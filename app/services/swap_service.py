"""Swap service: request/approve/reject/cancel setup swaps for an active reservation."""
from typing import List, Tuple

from app.core.config import settings
from app.core.constants import AuditAction, ReservationStatus, SetupStatus, SwapStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models.reservation import Reservation
from app.models.swap_request import SwapRequest
from app.models.user import User
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_swap_repository import ISwapRepository
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapFilter
from app.services.audit_service import AuditService


class SwapService:
    """Business logic for the swap-request workflow."""

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

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        return self._swap_repository.list(filters, page, page_size)

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
        old_reservation.status = ReservationStatus.SWAPPED
        self._reservation_repository.update(old_reservation)
        self._setup_repository.update_status(swap.current_setup_id, SetupStatus.AVAILABLE)

        new_reservation = Reservation(
            setup_id=swap.requested_setup_id,
            user_id=swap.requester_id,
            reserved_from=old_reservation.reserved_from,
            reserved_until=old_reservation.reserved_until,
            status=ReservationStatus.ACTIVE,
            purpose=old_reservation.purpose,
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
