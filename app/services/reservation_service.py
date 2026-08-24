"""
Reservation service.

The core aggregate of the system. Enforces the interval-overlap validation
rule (in the service layer, not the DB schema, since exclusion constraints
are not portable between SQLite and PostgreSQL -- see the architecture
document, section 11), keeps ``setup.status`` in sync with reservation
lifecycle transitions inside a single transaction, optionally broadcasts the
reservation across the requested announcement channels, and blocks
unreserving a reservation while a swap on it is still pending.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.constants import AuditAction, PermissionCode, ReservationStatus, SetupStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ReservationConflictError
from app.models.reservation import Reservation
from app.models.user import User
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_swap_repository import ISwapRepository
from app.schemas.reservation import ReservationCreateRequest, ReservationFilter
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.role_lookup_service import RoleLookupService


class ReservationService:
    """Business logic for creating, cancelling, and querying Reservations."""

    def __init__(
        self,
        reservation_repository: IReservationRepository,
        setup_repository: ISetupRepository,
        role_lookup_service: RoleLookupService,
        audit_service: AuditService,
        swap_repository: Optional[ISwapRepository] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self._reservation_repository = reservation_repository
        self._setup_repository = setup_repository
        self._role_lookup_service = role_lookup_service
        self._audit_service = audit_service
        self._swap_repository = swap_repository
        self._notification_service = notification_service

    def get_by_id(self, reservation_id: int) -> Reservation:
        reservation = self._reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError("Reservation with id {0} was not found.".format(reservation_id))
        return reservation

    def list(self, filters: ReservationFilter, page: int, page_size: int) -> Tuple[List[Reservation], int]:
        return self._reservation_repository.list(filters, page, page_size)

    def list_all(self, filters: ReservationFilter) -> List[Reservation]:
        """Return every reservation matching the filters, unpaginated (used by the web layer to join against setups)."""
        return self._reservation_repository.list_all(filters)

    def create(self, payload: ReservationCreateRequest, acting_user: User) -> Reservation:
        """
        Create a new reservation after validating the setup exists, is not
        retired/under maintenance, and that the requested window does not
        overlap any existing ACTIVE reservation on that setup. If
        ``announcement_channels`` were selected, broadcasts the reservation
        across them after the reservation is committed.
        """
        setup = self._setup_repository.get_by_id(payload.setup_id)
        if setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(payload.setup_id))
        if setup.status in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED):
            raise ConflictError("Setup is currently {0} and cannot be reserved.".format(setup.status.lower()))

        self._assert_no_overlap(payload.setup_id, payload.reserved_from, payload.reserved_until)

        reservation = Reservation(
            setup_id=payload.setup_id,
            user_id=acting_user.id,
            reserved_from=payload.reserved_from,
            reserved_until=payload.reserved_until,
            status=ReservationStatus.ACTIVE,
            remarks=payload.remarks,
        )
        created = self._reservation_repository.create(reservation)
        self._setup_repository.update_status(setup.id, SetupStatus.RESERVED)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="Reservation",
            entity_id=created.id,
            new_value={
                "setup_id": created.setup_id,
                "reserved_from": created.reserved_from,
                "reserved_until": created.reserved_until,
            },
        )

        if payload.announcement_channels and self._notification_service is not None:
            self._notification_service.broadcast_reservation_event(
                channels=payload.announcement_channels,
                message=payload.announcement_message,
                setup=setup,
                acting_user=acting_user,
            )

        return created

    def _assert_no_overlap(
        self, setup_id: int, reserved_from: datetime, reserved_until: datetime, exclude_reservation_id: Optional[int] = None
    ) -> None:
        """
        Raise ReservationConflictError if any ACTIVE reservation on the
        given setup overlaps the requested window.
        """
        overlapping = self._reservation_repository.find_overlapping(
            setup_id=setup_id,
            reserved_from=reserved_from,
            reserved_until=reserved_until,
            exclude_reservation_id=exclude_reservation_id,
        )
        if overlapping:
            raise ReservationConflictError(
                "Setup is already reserved for an overlapping time window.",
                details={"setup_id": setup_id, "conflicting_reservation_id": overlapping[0].id},
            )

    def cancel(self, reservation_id: int, acting_user: User) -> Reservation:
        """
        Cancel (unreserve) an ACTIVE reservation, freeing its setup.

        Raises:
            AuthorizationError: if the acting user does not own the
                reservation and lacks the ``reservation:cancel_any``
                permission.
            ConflictError: if the reservation is not ACTIVE, or if a swap
                request on this reservation is still PENDING (the swap must
                be approved, rejected, or cancelled -- "restored" -- first,
                so a mid-flight swap is never left dangling).
        """
        reservation = self.get_by_id(reservation_id)
        if reservation.status != ReservationStatus.ACTIVE:
            raise ConflictError("Only ACTIVE reservations can be cancelled.")

        if self._swap_repository is not None:
            pending_swap = self._swap_repository.get_pending_by_reservation_id(reservation_id)
            if pending_swap is not None:
                raise ConflictError(
                    "Cannot unreserve: a swap request on this reservation is still PENDING. "
                    "Approve, reject, or cancel the swap first to restore it.",
                    details={"pending_swap_request_id": pending_swap.id},
                )

        is_owner = reservation.user_id == acting_user.id
        can_cancel_any = self._role_lookup_service.role_has_permission(
            acting_user.role, PermissionCode.RESERVATION_CANCEL_ANY
        )
        if not is_owner and not can_cancel_any:
            raise AuthorizationError("You may only cancel your own reservations.")

        reservation.status = ReservationStatus.CANCELLED
        updated = self._reservation_repository.update(reservation)
        self._setup_repository.update_status(reservation.setup_id, SetupStatus.AVAILABLE)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CANCEL,
            entity_type="Reservation",
            entity_id=updated.id,
        )
        return updated

    def sweep_expired_reservations(self, as_of: datetime) -> int:
        """
        Background-job entry point: transition every ACTIVE reservation past
        its ``reserved_until`` to COMPLETED, free the corresponding setup
        back to AVAILABLE, and -- since it was not manually unreserved in
        time -- notify the setup's owner and the reserving user (CRITICAL
        wall announcement + email). Returns the number of reservations swept.
        """
        expired = self._reservation_repository.list_expired_active(as_of)
        for reservation in expired:
            setup = self._setup_repository.get_by_id(reservation.setup_id)
            reservation.status = ReservationStatus.COMPLETED
            self._reservation_repository.update(reservation)
            self._setup_repository.update_status(reservation.setup_id, SetupStatus.AVAILABLE)
            self._audit_service.record(
                user_id=None,
                action=AuditAction.UPDATE,
                entity_type="Reservation",
                entity_id=reservation.id,
                new_value={"status": ReservationStatus.COMPLETED, "reason": "scheduled_expiry_sweep"},
            )
            if self._notification_service is not None and setup is not None:
                self._notification_service.notify_reservation_expired(reservation, setup)
        return len(expired)
