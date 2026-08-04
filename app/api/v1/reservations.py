"""Reservation endpoints: create, list, get, cancel (unreserve)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_reservation_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.reservation import ReservationCreateRequest, ReservationFilter, ReservationResponse
from app.services.reservation_service import ReservationService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.get("", response_model=PaginatedResponse[ReservationResponse])
def list_reservations(
    user_id: Optional[int] = None,
    setup_id: Optional[int] = None,
    status: Optional[str] = None,
    reserved_from_after: Optional[datetime] = None,
    reserved_until_before: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.RESERVATION_VIEW)),
    reservation_service: ReservationService = Depends(get_reservation_service),
) -> PaginatedResponse:
    """List reservations with optional filters. Requires ``reservation:view``."""
    filters = ReservationFilter(
        user_id=user_id, setup_id=setup_id, status=status,
        reserved_from_after=reserved_from_after, reserved_until_before=reserved_until_before,
    )
    items, total_items = reservation_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=ReservationResponse, status_code=201)
def create_reservation(
    payload: ReservationCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.RESERVATION_CREATE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
):
    """Create a Reservation for the current user. Requires ``reservation:create``."""
    return reservation_service.create(payload, current_user)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.RESERVATION_VIEW)),
    reservation_service: ReservationService = Depends(get_reservation_service),
):
    """Fetch a single Reservation by id. Requires ``reservation:view``."""
    return reservation_service.get_by_id(reservation_id)


@router.patch("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    reservation_service: ReservationService = Depends(get_reservation_service),
):
    """
    Cancel (unreserve) a Reservation, freeing its Setup. Callable by the
    owning user, or by any user holding ``reservation:cancel_any``.
    """
    return reservation_service.cancel(reservation_id, current_user)
