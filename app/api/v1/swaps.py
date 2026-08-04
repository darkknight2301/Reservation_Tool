"""Swap request endpoints: request, approve, reject, cancel."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_swap_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapFilter, SwapResponse
from app.services.swap_service import SwapService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/swaps", tags=["Swaps"])


@router.get("", response_model=PaginatedResponse[SwapResponse])
def list_swaps(
    status: Optional[str] = None,
    requester_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.SWAP_VIEW)),
    swap_service: SwapService = Depends(get_swap_service),
) -> PaginatedResponse:
    """List swap requests with optional filters. Requires ``swap:view``."""
    filters = SwapFilter(status=status, requester_id=requester_id)
    items, total_items = swap_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=SwapResponse, status_code=201)
def create_swap(
    payload: SwapCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.SWAP_REQUEST)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Request a swap of the current user's active reservation. Requires ``swap:request``."""
    return swap_service.create(payload, current_user)


@router.get("/{swap_id}", response_model=SwapResponse)
def get_swap(
    swap_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.SWAP_VIEW)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Fetch a single swap request by id. Requires ``swap:view``."""
    return swap_service.get_by_id(swap_id)


@router.patch("/{swap_id}/approve", response_model=SwapResponse)
def approve_swap(
    swap_id: int,
    payload: SwapDecisionRequest,
    current_user: User = Depends(require_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Approve a pending swap request. Requires ``swap:approve``."""
    return swap_service.approve(swap_id, payload, current_user)


@router.patch("/{swap_id}/reject", response_model=SwapResponse)
def reject_swap(
    swap_id: int,
    payload: SwapDecisionRequest,
    current_user: User = Depends(require_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Reject a pending swap request. Requires ``swap:approve``."""
    return swap_service.reject(swap_id, payload, current_user)


@router.patch("/{swap_id}/cancel", response_model=SwapResponse)
def cancel_swap(
    swap_id: int,
    current_user: User = Depends(get_current_user),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Cancel the current user's own pending swap request."""
    return swap_service.cancel(swap_id, current_user)
