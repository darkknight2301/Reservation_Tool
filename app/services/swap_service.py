"""
Swap service.

Requests, approves, rejects, and cancels a hardware-field-value exchange
between two setups (business rule 5: both setups must contain the selected
column/hardware field). Redesigned in Phase 3 -- see
ARCHITECTURE_ASSESSMENT.md section 3.2 and IMPLEMENTATION_PROGRESS.md:

  * A Swap NEVER relocates, creates, or otherwise touches any Reservation,
    and NEVER changes a Setup's ``status``. It only ever changes the
    CURRENT/EFFECTIVE hardware field value(s) on the two Setup rows
    involved, once approved -- Reservation, Swap, and Borrow are
    independent workflows (business rule 1).
  * Every approved change is recorded as a ``HardwareChangeLog`` row (the
    Phase 1 append-only ledger), in addition to the existing
    ``previous_*_value`` snapshot kept on the SwapRequest itself and the
    general ``AuditLog``. The setup's ORIGINAL ``SetupHardwareBaseline`` is
    never touched by a Swap.
  * Approval is routed through the data-driven approval hierarchy
    (``ApprovalRoutingService``, walking ``group_hierarchy_edges``): if the
    current setup's owning Group (or an ancestor of it) has a Lead/Manager,
    only one of them (ANY ONE is sufficient -- OR semantics) or an Owner may
    approve. If no such user can be resolved anywhere in the hierarchy
    (e.g. no hierarchy configured yet and the group has no Lead of its
    own), approval falls back to the flat ``swap:approve`` permission
    (already enforced at the API/web layer) exactly as before Phase 3, so
    an approval can never become permanently unreachable.
  * The multi-node "swap mapping" feature (coordinated reservation
    relocation across several setups at once) has been removed entirely
    per business rule 6 ("remove/avoid swap-mapping functionality").
    Historical mapping-era rows remain in the database and are still
    readable via ``SwapResponse.batch_id``, but no new mapping can be
    created or approved.
"""
from typing import Dict, List, Optional, Tuple

from app.core.constants import (
    AnnouncementChannel,
    AuditAction,
    HardwareChangeSource,
    RoleName,
    SetupStatus,
    SwapStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationAppError
from app.models.hardware_change_log import HardwareChangeLog
from app.models.reservation import Reservation
from app.models.swap_request import SwapRequest
from app.models.user import User
from app.repositories.interfaces.i_hardware_change_log_repository import IHardwareChangeLogRepository
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_swap_repository import ISwapRepository
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapFilter
from app.services.approval_routing_service import ApprovalRoutingService
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

# Roles that may always approve a swap regardless of hierarchy routing
# (business rule 8: hierarchy affects routing, not general access -- Owner's
# blanket authority is a general-access fact, not something the hierarchy
# needs to grant).
_UNIVERSAL_APPROVER_ROLES = (RoleName.OWNER,)


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
    import json

    if len(values) == 1:
        (only_value,) = values.values()
        return None if only_value is None else str(only_value)
    return json.dumps({key: (None if value is None else str(value)) for key, value in values.items()})


class SwapService:
    """Business logic for single hardware-field-value swap requests."""

    def __init__(
        self,
        swap_repository: ISwapRepository,
        reservation_repository: IReservationRepository,
        setup_repository: ISetupRepository,
        audit_service: AuditService,
        hardware_change_log_repository: Optional[IHardwareChangeLogRepository] = None,
        approval_routing_service: Optional[ApprovalRoutingService] = None,
        template_service: Optional[TemplateService] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self._swap_repository = swap_repository
        self._reservation_repository = reservation_repository
        self._setup_repository = setup_repository
        self._audit_service = audit_service
        self._hardware_change_log_repository = hardware_change_log_repository
        self._approval_routing_service = approval_routing_service
        self._template_service = template_service
        self._notification_service = notification_service

    def get_by_id(self, swap_id: int) -> SwapRequest:
        swap = self._swap_repository.get_by_id(swap_id)
        if swap is None:
            raise NotFoundError("Swap request with id {0} was not found.".format(swap_id))
        return swap

    def get_pending_for_reservation(self, reservation_id: int):
        """Return the PENDING swap request on a reservation, if any (informational -- used to flag, not block, unreserving)."""
        return self._swap_repository.get_pending_by_reservation_id(reservation_id)

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        return self._swap_repository.list(filters, page, page_size)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_reservation_for_setup(self, setup_id: int) -> Optional[Reservation]:
        return self._reservation_repository.get_active_by_setup_id(setup_id)

    def _common_swappable_columns(self, setup_a, setup_b) -> List[str]:
        """
        Every column name that can legally be swapped between these two
        setups (business rule 5: both setups must contain the field): the
        fixed hardware fields (always available on every setup), plus --
        when the two setups belong to different products -- only the
        custom template columns present on *both* products' templates
        (same product: all of that product's custom columns).
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

    def _resolve_approver_emails(self, group_id: Optional[int]) -> List[str]:
        if self._approval_routing_service is None:
            return []
        approvers = self._approval_routing_service.resolve_approvers_for_group(group_id)
        return [user.email for user in approvers if user.email]

    def _assert_can_approve(self, swap: SwapRequest, current_setup, acting_user: User) -> None:
        """
        Enforce hierarchy-routed approval (see module docstring). The
        caller (API/web router) has already verified the acting user holds
        the flat ``swap:approve`` permission -- this narrows *which*
        permission-holder may act on *this particular* request.
        """
        if acting_user.role and acting_user.role.name in _UNIVERSAL_APPROVER_ROLES:
            return
        if self._approval_routing_service is None:
            return  # No routing configured for this service instance -- flat permission check is authoritative.

        approvers = self._approval_routing_service.resolve_approvers_for_group(current_setup.group_id)
        if not approvers:
            return  # Fallback: no one is resolvable via the hierarchy -- flat swap:approve permission is authoritative.

        if acting_user.id not in {user.id for user in approvers}:
            raise AuthorizationError(
                "You are not one of the routed approvers for this setup's group. "
                "Any one of that group's (or an ancestor group's) Lead/Manager may approve this swap."
            )

    # ------------------------------------------------------------------
    # Request / approve / reject / cancel
    # ------------------------------------------------------------------

    def create(self, payload: SwapCreateRequest, acting_user: User) -> SwapRequest:
        if payload.requested_setup_id == payload.current_setup_id:
            raise ConflictError("Requested setup must differ from the current setup.")

        current_setup = self._setup_repository.get_by_id(payload.current_setup_id)
        if current_setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(payload.current_setup_id))
        requested_setup = self._setup_repository.get_by_id(payload.requested_setup_id)
        if requested_setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(payload.requested_setup_id))

        for setup in (current_setup, requested_setup):
            if setup.status in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED):
                raise ConflictError("Setup {0} is currently {1} and cannot be part of a swap.".format(setup.hostname, setup.status.lower()))

        # Ownership precondition: the requester must currently be the one
        # using the setup whose hardware they're proposing to change. This
        # is an access/ownership rule (business rule 8), not a structural
        # dependency -- Swap does not require this reservation to remain
        # active for the request to be approved later (see approve()), it
        # only requires it to exist *right now*, to identify who may ask.
        active_reservation = self._active_reservation_for_setup(current_setup.id)
        if active_reservation is None or active_reservation.user_id != acting_user.id:
            raise AuthorizationError("You may only request a swap for a setup you currently have an ACTIVE reservation on.")

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

        routed_emails = self._resolve_approver_emails(current_setup.group_id)

        swap = SwapRequest(
            reservation_id=active_reservation.id,  # informational only (see model docstring) -- never used to gate approval
            requester_id=acting_user.id,
            current_setup_id=current_setup.id,
            requested_setup_id=requested_setup.id,
            column_name=_encode_columns(resolved_columns),
            status=SwapStatus.PENDING,
            reason=payload.reason,
            start_time=payload.start_time,
            end_time=payload.end_time,
            announcement_channels=",".join(payload.announcement_channels) if payload.announcement_channels else None,
            routed_approver_emails=",".join(routed_emails) if routed_emails else None,
        )
        created = self._swap_repository.create(swap)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="SwapRequest",
            entity_id=created.id,
            new_value={
                "current_setup_id": current_setup.id, "requested_setup_id": requested_setup.id,
                "column_names": resolved_columns,
            },
        )

        if self._notification_service is not None:
            message = payload.announcement_message or "{0} requested to swap {1} between {2} and {3}. Approval needed.".format(
                acting_user.full_name, ", ".join("'{0}'".format(name) for name in resolved_columns),
                current_setup.hostname, requested_setup.hostname,
            )
            subject = "Swap approval needed: {0}".format(current_setup.hostname)
            # The routed approvers ("applicable lead emails", business rule
            # 2) are always notified directly, regardless of the requested
            # announcement_channels -- they need to know to review it. The
            # broader broadcast (Wall / group / everyone) still respects the
            # requester's channel selection; MAIL_LEADS is stripped from it
            # since routed_emails already generalizes/supersedes it here.
            if routed_emails:
                self._notification_service.email_direct(routed_emails, subject, message)
            extra_channels = [c for c in payload.announcement_channels if c != AnnouncementChannel.MAIL_LEADS]
            if extra_channels:
                self._notification_service.broadcast_reservation_event(extra_channels, message, current_setup, acting_user)

        return created

    def approve(self, swap_id: int, payload: SwapDecisionRequest, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be approved.")

        current_setup = self._setup_repository.get_by_id(swap.current_setup_id)
        requested_setup = self._setup_repository.get_by_id(swap.requested_setup_id)
        if current_setup is None or requested_setup is None:
            raise NotFoundError("One of the setups in this swap request no longer exists.")

        for setup in (current_setup, requested_setup):
            if setup.status in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED):
                raise ConflictError("Setup {0} is currently {1} and this swap can no longer be applied.".format(setup.hostname, setup.status.lower()))

        self._assert_can_approve(swap, current_setup, acting_user)

        column_names = swap.column_names  # may be empty defensively, though create() never leaves it empty

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

        swap.status = SwapStatus.COMPLETED
        swap.approved_by_id = acting_user.id
        if payload.reason:
            swap.reason = payload.reason
        updated_swap = self._swap_repository.update(swap)

        # Append-only, per-field hardware change ledger (Phase 1) -- feeds
        # the Setup Table's "only changed cells highlighted" UI requirement.
        # Only the fixed hardware fields are logged here (SWAPPABLE_SETUP_FIELDS);
        # custom template-column history is tracked by TemplateService itself.
        if self._hardware_change_log_repository is not None:
            ledger_rows = []
            for column_name in column_names:
                if column_name not in SWAPPABLE_SETUP_FIELDS:
                    continue
                ledger_rows.append(HardwareChangeLog(
                    setup_id=current_setup.id, field_name=column_name,
                    old_value=None if old_values[column_name] is None else str(old_values[column_name]),
                    new_value=None if new_values[column_name] is None else str(new_values[column_name]),
                    source=HardwareChangeSource.SWAP, source_request_id=swap.id, changed_by_id=acting_user.id,
                ))
                ledger_rows.append(HardwareChangeLog(
                    setup_id=requested_setup.id, field_name=column_name,
                    old_value=None if new_values[column_name] is None else str(new_values[column_name]),
                    new_value=None if old_values[column_name] is None else str(old_values[column_name]),
                    source=HardwareChangeSource.SWAP, source_request_id=swap.id, changed_by_id=acting_user.id,
                ))
            if ledger_rows:
                self._hardware_change_log_repository.create_many(ledger_rows)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.APPROVE,
            entity_type="SwapRequest",
            entity_id=updated_swap.id,
            new_value={"column_names": column_names},
        )
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.UPDATE, entity_type="Setup", entity_id=current_setup.id,
            old_value=old_values, new_value=new_values,
        )
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.UPDATE, entity_type="Setup", entity_id=requested_setup.id,
            old_value=new_values, new_value=old_values,
        )
        return updated_swap

    def reject(self, swap_id: int, payload: SwapDecisionRequest, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be rejected.")

        current_setup = self._setup_repository.get_by_id(swap.current_setup_id)
        if current_setup is not None:
            self._assert_can_approve(swap, current_setup, acting_user)

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
