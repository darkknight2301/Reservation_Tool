"""
Swap service: request/approve/reject/cancel a column-value swap between two
of the requester's own reserved setups, and create/approve coordinated
multi-node swap mappings (A->B, B->A, C->D) that relocate reservations.
"""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.constants import AnnouncementChannel, AuditAction, ReservationStatus, SetupStatus, SwapStatus
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    SwapMappingValidationError,
    ValidationAppError,
)
from app.models.reservation import Reservation
from app.models.swap_request import SwapRequest
from app.models.user import User
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_swap_repository import ISwapRepository
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapFilter, SwapMappingCreateRequest
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.template_service import TemplateService

# Fixed Setup columns eligible for a column swap (hardware/asset fields only
# -- identity fields like ip_address/hostname and lifecycle fields like
# status/remarks are never swappable).
SWAPPABLE_SETUP_FIELDS = (
    "ssd", "hdd", "hardware_info", "capacity", "form_factor",
    "adapter", "aardvark", "quarch", "apc", "remote_server",
)


def _format_swap_remark(
    user_email: str, from_hostname: str, to_hostname: str, column_names: List[str],
    old_values: Dict[str, object], new_values: Dict[str, object], at: datetime,
) -> str:
    """
    Build the swap history line appended to the reservation's remarks (and
    thus visible to every viewer via the Setup Table's Remarks column):
    who swapped which column(s), between which setups, each original vs new
    value (so it can be restored later), and when.
    """
    changes = ", ".join(
        "'{0}' ({1} -> {2})".format(
            name,
            old_values.get(name) if old_values.get(name) is not None else "(empty)",
            new_values.get(name) if new_values.get(name) is not None else "(empty)",
        )
        for name in column_names
    )
    return "{0} swapped {1} between {2} and {3} at {4}".format(
        user_email, changes, from_hostname, to_hostname, at.strftime("%H:%M %d/%m/%Y"),
    )


def _encode_columns(column_names: List[str]) -> str:
    """Store the swapped column name(s) as a comma-separated string in ``SwapRequest.column_name``."""
    return ",".join(column_names)


def _encode_value_map(values: Dict[str, object]) -> Optional[str]:
    """
    Store a {column_name: value} map in a ``previous_*_value`` field.

    For the common single-column case this stores the plain value itself
    (unchanged format from before multi-column support existed); for a
    multi-column swap it stores compact JSON so each column's prior value
    can still be recovered.
    """
    if len(values) == 1:
        (only_value,) = values.values()
        return None if only_value is None else str(only_value)
    return json.dumps({key: (None if value is None else str(value)) for key, value in values.items()})


def _format_relocation_remark(user_email: str, from_hostname: str, to_hostname: str, at: datetime) -> str:
    """Build the reservation-relocation history line used by the multi-node swap mapping flow."""
    return "{0} relocated reservation from {1} to {2} at {3}".format(
        user_email, from_hostname, to_hostname, at.strftime("%H:%M %d/%m/%Y")
    )


def _append_remark(existing: str, new_line: str) -> str:
    return "{0}\n{1}".format(existing, new_line) if existing else new_line


class SwapService:
    """Business logic for single swap requests and multi-node swap mappings."""

    def __init__(
        self,
        swap_repository: ISwapRepository,
        reservation_repository: IReservationRepository,
        setup_repository: ISetupRepository,
        audit_service: AuditService,
        template_service: Optional[TemplateService] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self._swap_repository = swap_repository
        self._reservation_repository = reservation_repository
        self._setup_repository = setup_repository
        self._audit_service = audit_service
        self._template_service = template_service
        self._notification_service = notification_service

    def get_by_id(self, swap_id: int) -> SwapRequest:
        swap = self._swap_repository.get_by_id(swap_id)
        if swap is None:
            raise NotFoundError("Swap request with id {0} was not found.".format(swap_id))
        return swap

    def get_pending_for_reservation(self, reservation_id: int):
        """Return the PENDING swap request on a reservation, if any (used to warn before unreserving)."""
        return self._swap_repository.get_pending_by_reservation_id(reservation_id)

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        return self._swap_repository.list(filters, page, page_size)

    # ------------------------------------------------------------------
    # Single column-value swap between two of the requester's own setups
    # ------------------------------------------------------------------

    def _active_reservation_for_setup(self, setup_id: int) -> Optional[Reservation]:
        return self._reservation_repository.get_active_by_setup_id(setup_id)

    def _common_swappable_columns(self, setup_a, setup_b) -> List[str]:
        """
        Every column name that can legally be swapped between these two
        setups: the fixed hardware fields (always available on every
        setup), plus -- when the two setups belong to different products --
        only the custom template columns present on *both* products'
        templates (same product: all of that product's custom columns).
        """
        columns = list(SWAPPABLE_SETUP_FIELDS)
        if self._template_service is None:
            return columns

        names_a = {c.name for c in self._template_service.get_custom_columns(setup_a.product_id)}
        if setup_a.product_id == setup_b.product_id:
            columns.extend(sorted(names_a))
        else:
            names_b = {c.name for c in self._template_service.get_custom_columns(setup_b.product_id)}
            columns.extend(sorted(names_a & names_b))
        return columns

    def create(self, payload: SwapCreateRequest, acting_user: User) -> SwapRequest:
        reservation = self._reservation_repository.get_by_id(payload.reservation_id)
        if reservation is None:
            raise NotFoundError("Reservation with id {0} was not found.".format(payload.reservation_id))
        if reservation.user_id != acting_user.id:
            raise AuthorizationError("You may only request a swap for your own reservation.")
        if reservation.status != ReservationStatus.ACTIVE:
            raise ConflictError("Only an ACTIVE reservation can be swapped.")
        if payload.requested_setup_id == reservation.setup_id:
            raise ConflictError("Requested setup must differ from the current setup.")

        requested_setup = self._setup_repository.get_by_id(payload.requested_setup_id)
        if requested_setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(payload.requested_setup_id))

        # Rule: the target must be a free (AVAILABLE) setup -- not one someone
        # else is actively using, under maintenance, or retired. It does NOT
        # need to already be reserved by the requester: this is a request to
        # relocate/exchange configuration with an idle setup, which the
        # approver signs off on before it takes effect.
        if requested_setup.status != SetupStatus.AVAILABLE:
            raise ConflictError("The requested setup must also be one of your own currently-reserved setups.")

        current_setup = self._setup_repository.get_by_id(reservation.setup_id)
        allowed_columns = self._common_swappable_columns(current_setup, requested_setup)

        requested_columns = payload.resolved_column_names()
        if requested_columns is None:
            # No column(s) specified -- swap every column common to both setups.
            if not allowed_columns:
                raise ValidationAppError("These two setups have no swappable columns in common.")
            resolved_columns = allowed_columns
        else:
            invalid = [name for name in requested_columns if name not in allowed_columns]
            if invalid:
                raise ValidationAppError(
                    "The following column(s) are not swappable / not common to both setups: {0}.".format(
                        ", ".join(invalid)
                    )
                )
            resolved_columns = requested_columns

        swap = SwapRequest(
            reservation_id=reservation.id,
            requester_id=acting_user.id,
            current_setup_id=reservation.setup_id,
            requested_setup_id=payload.requested_setup_id,
            column_name=_encode_columns(resolved_columns),
            status=SwapStatus.PENDING,
            reason=payload.reason,
        )
        created = self._swap_repository.create(swap)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="SwapRequest",
            entity_id=created.id,
            new_value={
                "reservation_id": reservation.id, "requested_setup_id": payload.requested_setup_id,
                "column_names": resolved_columns,
            },
        )

        if self._notification_service is not None:
            message = "{0} requested to swap {1} between {2} and {3}. Approval needed.".format(
                acting_user.full_name, ", ".join("'{0}'".format(name) for name in resolved_columns),
                current_setup.hostname, requested_setup.hostname,
            )
            self._notification_service.broadcast_reservation_event(
                [AnnouncementChannel.MAIL_LEADS], message, current_setup, acting_user
            )
        return created

    def approve(self, swap_id: int, payload: SwapDecisionRequest, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be approved.")

        current_setup = self._setup_repository.get_by_id(swap.current_setup_id)
        requested_setup = self._setup_repository.get_by_id(swap.requested_setup_id)
        if current_setup is None or requested_setup is None:
            raise NotFoundError("One of the setups in this swap request no longer exists.")

        # Re-verify the current reservation is still active, and the target
        # setup is still free -- a swap never touches reservation/setup
        # status itself, only the exchanged value(s).
        current_active = self._active_reservation_for_setup(swap.current_setup_id)
        if current_active is None or current_active.user_id != swap.requester_id:
            raise ConflictError("The requester's reservation on the current setup is no longer active.")
        if requested_setup.status != SetupStatus.AVAILABLE:
            raise ConflictError("The requested setup is no longer available to swap into.")

        column_names = swap.column_names  # may be empty: a pure relocation, no column value exchange

        template_values_a: Optional[Dict] = None
        template_values_b: Optional[Dict] = None
        old_values: Dict[str, object] = {}
        new_values: Dict[str, object] = {}

        for column_name in column_names:
            if column_name in SWAPPABLE_SETUP_FIELDS:
                old_value = getattr(current_setup, column_name)
                value_b = getattr(requested_setup, column_name)
                setattr(current_setup, column_name, value_b)
                setattr(requested_setup, column_name, old_value)
            elif self._template_service is not None:
                if template_values_a is None:
                    template_values_a = self._template_service.get_values_map_for_setup(
                        current_setup.id, current_setup.product_id
                    )
                    template_values_b = self._template_service.get_values_map_for_setup(
                        requested_setup.id, requested_setup.product_id
                    )
                old_value = template_values_a.get(column_name)
                value_b = template_values_b.get(column_name)
                self._template_service.set_setup_values(
                    current_setup.id, current_setup.product_id, {column_name: value_b}, acting_user
                )
                self._template_service.set_setup_values(
                    requested_setup.id, requested_setup.product_id, {column_name: old_value}, acting_user
                )
            else:
                raise ValidationAppError("Template-aware swap is not configured; cannot swap a custom column.")

            old_values[column_name] = old_value
            new_values[column_name] = value_b

        self._setup_repository.update(current_setup)
        self._setup_repository.update(requested_setup)

        if column_names:
            # Record what each setup's value(s) were *before* the exchange --
            # visible to anyone with swap:view (every role) via SwapResponse,
            # so the original configuration can be restored later (e.g. via
            # Setup Edit) even without digging through the Manager/Owner-only
            # audit log. Stored as {column_name: value} JSON since a request
            # can now cover more than one column.
            swap.previous_current_value = _encode_value_map(old_values)
            swap.previous_requested_value = _encode_value_map(new_values)

        # Relocate the reservation itself: the original reservation ends
        # (SWAPPED), the current setup is freed, and a new ACTIVE reservation
        # is created for the requester on the target setup -- mirroring the
        # multi-node mapping flow in approve_mapping() below.
        now = datetime.utcnow()
        if column_names:
            remark = _format_swap_remark(
                swap.requester.email if swap.requester else "unknown", current_setup.hostname,
                requested_setup.hostname, column_names, old_values, new_values, now,
            )
        else:
            remark = _format_relocation_remark(
                swap.requester.email if swap.requester else "unknown", current_setup.hostname,
                requested_setup.hostname, now,
            )

        old_reservation = self._reservation_repository.get_by_id(swap.reservation_id)
        new_reservation = None
        if old_reservation is not None:
            carried_remarks = _append_remark(old_reservation.remarks, remark)
            old_reservation.status = ReservationStatus.SWAPPED
            old_reservation.remarks = carried_remarks
            self._reservation_repository.update(old_reservation)

            new_reservation = self._reservation_repository.create(Reservation(
                setup_id=swap.requested_setup_id,
                user_id=swap.requester_id,
                reserved_from=old_reservation.reserved_from,
                reserved_until=old_reservation.reserved_until,
                status=ReservationStatus.ACTIVE,
                remarks=carried_remarks,
            ))

        self._setup_repository.update_status(swap.current_setup_id, SetupStatus.AVAILABLE)
        self._setup_repository.update_status(swap.requested_setup_id, SetupStatus.RESERVED)

        swap.status = SwapStatus.COMPLETED
        swap.approved_by_id = acting_user.id
        if payload.reason:
            swap.reason = payload.reason
        updated_swap = self._swap_repository.update(swap)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.APPROVE,
            entity_type="SwapRequest",
            entity_id=updated_swap.id,
            new_value={"column_names": column_names},
        )
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.SWAP,
            entity_type="Reservation",
            entity_id=(new_reservation.id if new_reservation is not None else swap.reservation_id),
            old_value={"setup_id": swap.current_setup_id, "column_names": column_names},
            new_value={"setup_id": swap.requested_setup_id},
        )
        return updated_swap

    def reject(self, swap_id: int, payload: SwapDecisionRequest, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be rejected.")
        swap.status = SwapStatus.REJECTED
        swap.approved_by_id = acting_user.id
        if payload.reason:
            swap.reason = payload.reason
        updated = self._swap_repository.update(swap)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.REJECT,
            entity_type="SwapRequest",
            entity_id=updated.id,
        )
        return updated

    def cancel(self, swap_id: int, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.requester_id != acting_user.id:
            raise AuthorizationError("You may only cancel your own swap request.")
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be cancelled.")
        swap.status = SwapStatus.CANCELLED
        updated = self._swap_repository.update(swap)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CANCEL,
            entity_type="SwapRequest",
            entity_id=updated.id,
        )
        return updated

    # ------------------------------------------------------------------
    # Multi-node swap mapping (A->B, B->A, C->D)
    # ------------------------------------------------------------------

    def create_mapping(self, payload: SwapMappingCreateRequest, acting_user: User) -> List[SwapRequest]:
        """
        Validate and create a coordinated multi-node swap mapping as a set
        of PENDING SwapRequest rows sharing one ``batch_id``.

        Validation ("every node appears once; reject invalid swaps"):
          - Every ``reservation_id`` in the mapping must be distinct and ACTIVE.
          - Every ``target_setup_id`` must be distinct.
          - A target setup that is *not* itself a source setup within this
            same mapping (i.e. not part of the cycle) must currently be
            AVAILABLE -- it isn't being vacated by anything else in the batch.
          - A reservation may not target its own current setup.
        """
        if len(payload.mappings) < 2:
            raise SwapMappingValidationError("A swap mapping requires at least two entries.")

        reservation_ids = [entry.reservation_id for entry in payload.mappings]
        target_setup_ids = [entry.target_setup_id for entry in payload.mappings]

        if len(set(reservation_ids)) != len(reservation_ids):
            raise SwapMappingValidationError("Every reservation may appear at most once in the mapping.")
        if len(set(target_setup_ids)) != len(target_setup_ids):
            raise SwapMappingValidationError("Every target setup may appear at most once in the mapping.")

        reservations_by_id: Dict[int, Reservation] = {}
        source_setup_ids = set()
        for reservation_id in reservation_ids:
            reservation = self._reservation_repository.get_by_id(reservation_id)
            if reservation is None:
                raise NotFoundError("Reservation with id {0} was not found.".format(reservation_id))
            if reservation.status != ReservationStatus.ACTIVE:
                raise SwapMappingValidationError(
                    "Reservation {0} is not ACTIVE and cannot be included in a swap mapping.".format(reservation_id)
                )
            reservations_by_id[reservation_id] = reservation
            source_setup_ids.add(reservation.setup_id)

        if len(source_setup_ids) != len(reservation_ids):
            raise SwapMappingValidationError("Two reservations in the mapping resolve to the same current setup.")

        for entry in payload.mappings:
            reservation = reservations_by_id[entry.reservation_id]
            if entry.target_setup_id == reservation.setup_id:
                raise SwapMappingValidationError(
                    "Reservation {0} cannot target its own current setup.".format(entry.reservation_id)
                )
            if entry.target_setup_id not in source_setup_ids:
                target_setup = self._setup_repository.get_by_id(entry.target_setup_id)
                if target_setup is None:
                    raise NotFoundError("Setup with id {0} was not found.".format(entry.target_setup_id))
                if target_setup.status != SetupStatus.AVAILABLE:
                    raise SwapMappingValidationError(
                        "Target setup {0} is not part of the swap cycle and is not currently AVAILABLE.".format(
                            entry.target_setup_id
                        )
                    )

        batch_id = str(uuid.uuid4())
        swap_requests = [
            SwapRequest(
                reservation_id=entry.reservation_id,
                requester_id=acting_user.id,
                current_setup_id=reservations_by_id[entry.reservation_id].setup_id,
                requested_setup_id=entry.target_setup_id,
                status=SwapStatus.PENDING,
                reason=payload.reason,
                batch_id=batch_id,
            )
            for entry in payload.mappings
        ]
        created = self._swap_repository.create_many(swap_requests)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="SwapRequestMapping",
            entity_id=None,
            new_value={"batch_id": batch_id, "entries": len(created)},
        )
        return created

    def approve_mapping(self, batch_id: str, acting_user: User) -> List[SwapRequest]:
        """
        Approve every PENDING SwapRequest in a mapping batch atomically:
        all reservations move to their target setups together, with setups
        that are targets-within-the-batch never passing through AVAILABLE.
        """
        batch = self._swap_repository.list_by_batch_id(batch_id)
        if not batch:
            raise NotFoundError("Swap mapping batch '{0}' was not found.".format(batch_id))
        if any(swap.status != SwapStatus.PENDING for swap in batch):
            raise ConflictError("Every swap request in the batch must still be PENDING to approve the mapping.")

        source_setup_ids = {swap.current_setup_id for swap in batch}
        now = datetime.utcnow()

        old_reservations: Dict[int, Reservation] = {}
        for swap in batch:
            reservation = self._reservation_repository.get_by_id(swap.reservation_id)
            if reservation is None or reservation.status != ReservationStatus.ACTIVE:
                raise ConflictError("Reservation {0} is no longer ACTIVE; the mapping can no longer be applied.".format(swap.reservation_id))
            old_reservations[swap.id] = reservation

        created_reservations: List[Reservation] = []
        for swap in batch:
            old_reservation = old_reservations[swap.id]
            current_setup = self._setup_repository.get_by_id(swap.current_setup_id)
            target_setup = self._setup_repository.get_by_id(swap.requested_setup_id)
            remark = _format_relocation_remark(old_reservation.user.email, current_setup.hostname, target_setup.hostname, now)
            carried_remarks = _append_remark(old_reservation.remarks, remark)

            old_reservation.status = ReservationStatus.SWAPPED
            old_reservation.remarks = carried_remarks
            self._reservation_repository.update(old_reservation)

            new_reservation = Reservation(
                setup_id=swap.requested_setup_id,
                user_id=swap.requester_id,
                reserved_from=old_reservation.reserved_from,
                reserved_until=old_reservation.reserved_until,
                status=ReservationStatus.ACTIVE,
                remarks=carried_remarks,
            )
            created_reservations.append(self._reservation_repository.create(new_reservation))

            swap.status = SwapStatus.COMPLETED
            swap.approved_by_id = acting_user.id
            self._swap_repository.update(swap)

        for setup_id in source_setup_ids:
            self._setup_repository.update_status(setup_id, SetupStatus.AVAILABLE)
        for swap in batch:
            self._setup_repository.update_status(swap.requested_setup_id, SetupStatus.RESERVED)

        for reservation, swap in zip(created_reservations, batch):
            self._audit_service.record(
                user_id=acting_user.id,
                action=AuditAction.SWAP,
                entity_type="Reservation",
                entity_id=reservation.id,
                old_value={"setup_id": swap.current_setup_id},
                new_value={"setup_id": swap.requested_setup_id, "batch_id": batch_id},
            )

        return batch
