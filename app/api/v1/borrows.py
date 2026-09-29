"""Borrow endpoints: request, approve, reject, cancel, return (Phase 5).

Independent from Reservation and Swap. Requesting/approving/returning is
restricted to Lead/Manager (and Owner) roles via the ``borrow:*``
permissions; who may act on one *particular* request is further narrowed by
``BorrowService`` (hierarchy-routed approval, requester/lead-only return).
"""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_borrow_service, get_current_user, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.borrow_request import (
    BorrowCreateRequest,
    BorrowDecisionRequest,
    BorrowFilter,
    BorrowResponse,
    BorrowReturnRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.borrow_service import BorrowService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/borrows", tags=["Borrows"])


@router.get("", response_model=PaginatedResponse[BorrowResponse])
def list_borrows(
    status: Optional[str] = None,
    requester_id: Optional[int] = None,
    setup_id: Optional[int] = None,
    group_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.BORROW_VIEW)),
    borrow_service: BorrowService = Depends(get_borrow_service),
) -> PaginatedResponse:
    """List borrow requests (full Borrow history when unfiltered). Requires ``borrow:view``."""
    filters = BorrowFilter(status=status, requester_id=requester_id, setup_id=setup_id, group_id=group_id)
    items, total_items = borrow_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=BorrowResponse, status_code=201)
def create_borrow(
    payload: BorrowCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.BORROW_REQUEST)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Request to borrow a setup (optionally one hardware field) from the selected source lead. Requires ``borrow:request``."""
    return borrow_service.create(payload, current_user)


@router.get("/{borrow_id}", response_model=BorrowResponse)
def get_borrow(
    borrow_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.BORROW_VIEW)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Fetch one borrow request. Requires ``borrow:view``."""
    return borrow_service.get_by_id(borrow_id)


@router.patch("/{borrow_id}/approve", response_model=BorrowResponse)
def approve_borrow(
    borrow_id: int,
    payload: BorrowDecisionRequest,
    current_user: User = Depends(require_permission(PermissionCode.BORROW_APPROVE)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Approve a pending borrow. Requires ``borrow:approve``; any ONE routed approver (or an Owner) suffices."""
    return borrow_service.approve(borrow_id, payload, current_user)


@router.patch("/{borrow_id}/reject", response_model=BorrowResponse)
def reject_borrow(
    borrow_id: int,
    payload: BorrowDecisionRequest,
    current_user: User = Depends(require_permission(PermissionCode.BORROW_APPROVE)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Reject a pending borrow. Requires ``borrow:approve``, subject to the same routing as approval."""
    return borrow_service.reject(borrow_id, payload, current_user)


@router.patch("/{borrow_id}/cancel", response_model=BorrowResponse)
def cancel_borrow(
    borrow_id: int,
    current_user: User = Depends(get_current_user),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Cancel the current user's own pending borrow request."""
    return borrow_service.cancel(borrow_id, current_user)


@router.patch("/{borrow_id}/return", response_model=BorrowResponse)
def return_borrow(
    borrow_id: int,
    payload: BorrowReturnRequest,
    current_user: User = Depends(require_permission(PermissionCode.BORROW_RETURN)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Return ("get back") a borrowed setup: closes the access grant and restores the source group's access. Requires ``borrow:return``."""
    return borrow_service.return_borrow(borrow_id, payload, current_user)
