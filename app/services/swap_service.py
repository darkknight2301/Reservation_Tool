"""
Swap service: request/approve/reject/cancel single setup swaps, and
create/approve coordinated multi-node swap mappings (A->B, B->A, C->D).
"""
import uuid
from datetime import datetime
from typing import Dict, List, Tuple

from app.core.config import settings
from app.core.constants import AuditAction, ReservationStatus, SetupStatus, SwapStatus
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    SwapMappingValidationError,
)
from app.models.reservation import Reservation
from app.models.swap_request import SwapRequest
from app.models.user import User
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_swap_repository import ISwapRepository
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapFilter, SwapMappingCreateRequest
from app.services.audit_service import AuditService


def _format_swap_remark(user_email: str, from_hostname: str, to_hostname: str, at: datetime) -> str:
    """Build the required swap history line: 'user@mail.com swapped drive from A to B at HH:MM DD/MM/YYYY'."""
    return "{0} swapped drive from {1} to {2} at {3}".format(
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
    ) -> None:
        self._swap_repository = swap_repository
        self._reservation_repository = reservation_repository
        self._setup_repository = setup_repository
        self._audit_service = audit_service

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
    # Single 1:1 swap
    # ------------------------------------------------------------------

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
        if requested_setup.status != SetupStatus.AVAILABLE:
            raise ConflictError("Requested setup is not currently AVAILABLE.")

        current_setup = self._setup_repository.get_by_id(reservation.setup_id)
        if settings.SWAP_REQUIRE_SAME_PRODUCT and current_setup.product_id != requested_setup.product_id:
            raise ConflictError("Requested setup must belong to the same product.")

        swap = SwapRequest(
            reservation_id=reservation.id,
            requester_id=acting_user.id,
            current_setup_id=reservation.setup_id,
            requested_setup_id=payload.requested_setup_id,
            status=SwapStatus.PENDING,
            reason=payload.reason,
        )
        created = self._swap_repository.create(swap)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="SwapRequest",
            entity_id=created.id,
            new_value={"reservation_id": reservation.id, "requested_setup_id": payload.requested_setup_id},
        )
        return created

    def approve(self, swap_id: int, payload: SwapDecisionRequest, acting_user: User) -> SwapRequest:
        swap = self.get_by_id(swap_id)
        if swap.status != SwapStatus.PENDING:
            raise ConflictError("Only a PENDING swap request can be approved.")

        requested_setup = self._setup_repository.get_by_id(swap.requested_setup_id)
        if requested_setup is None or requested_setup.status != SetupStatus.AVAILABLE:
            raise ConflictError("Requested setup is no longer AVAILABLE.")

        old_reservation = self._reservation_repository.get_by_id(swap.reservation_id)
        current_setup = self._setup_repository.get_by_id(swap.current_setup_id)
        now = datetime.utcnow()
        remark = _format_swap_remark(old_reservation.user.email, current_setup.hostname, requested_setup.hostname, now)
        carried_remarks = _append_remark(old_reservation.remarks, remark)

        old_reservation.status = ReservationStatus.SWAPPED
        old_reservation.remarks = carried_remarks
        self._reservation_repository.update(old_reservation)
        self._setup_repository.update_status(swap.current_setup_id, SetupStatus.AVAILABLE)

        new_reservation = Reservation(
            setup_id=swap.requested_setup_id,
            user_id=swap.requester_id,
            reserved_from=old_reservation.reserved_from,
            reserved_until=old_reservation.reserved_until,
            status=ReservationStatus.ACTIVE,
            remarks=carried_remarks,
        )
        created_reservation = self._reservation_repository.create(new_reservation)
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
            new_value={"new_reservation_id": created_reservation.id},
        )
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.SWAP,
            entity_type="Reservation",
            entity_id=created_reservation.id,
            old_value={"setup_id": swap.current_setup_id},
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
            remark = _format_swap_remark(old_reservation.user.email, current_setup.hostname, target_setup.hostname, now)
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
