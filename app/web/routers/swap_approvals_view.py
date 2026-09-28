"""
Swap Approvals screen: lists PENDING swap requests and lets a routed
approver (or, absent any hierarchy routing, anyone with ``swap:approve``)
approve or reject them one at a time.

Replaces the pre-Phase-3 ``/admin/swap-mapping`` page, which mixed this
single-swap approval concern together with the now-retired multi-node
swap-mapping feature (business rule 6). This page only ever calls
``SwapService.approve``/``reject`` -- never anything mapping-related.
"""
from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_swap_service
from app.core.constants import PermissionCode, SwapStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.swap_request import SwapDecisionRequest, SwapFilter
from app.services.swap_service import SwapService
from app.web.deps import base_context, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(prefix="/admin/swap-approvals", tags=["Web: Swap Approvals"])


def _pending_swaps_context(request: Request, current_user: User, swap_service: SwapService) -> dict:
    pending_swaps, _ = swap_service.list(SwapFilter(status=SwapStatus.PENDING), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"pending_swaps": pending_swaps})
    return context


@router.get("")
def swap_approvals_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Render the Swap Approvals page: every PENDING swap request."""
    return templates.TemplateResponse("admin/swap_approvals.html", _pending_swaps_context(request, current_user, swap_service))


@router.get("/list")
def swap_approvals_list_partial(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """HTMX partial: re-render the pending-swap list."""
    return templates.TemplateResponse("admin/_swap_approvals_list.html", _pending_swaps_context(request, current_user, swap_service))


@router.post("/{swap_id}/approve")
def approve_swap_web(
    request: Request,
    swap_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Approve a pending swap; subject to hierarchy routing (see ApprovalRoutingService)."""
    message, message_type = "Swap approved -- values have been exchanged.", "success"
    try:
        swap_service.approve(swap_id, SwapDecisionRequest(), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    response = templates.TemplateResponse("admin/_swap_approvals_list.html", _pending_swaps_context(request, current_user, swap_service))
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/{swap_id}/reject")
def reject_swap_web(
    request: Request,
    swap_id: int,
    rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Reject a pending swap; subject to the same hierarchy routing as approval."""
    message, message_type = "Swap request rejected.", "success"
    try:
        swap_service.reject(swap_id, SwapDecisionRequest(reason=rejection_reason or None), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    response = templates.TemplateResponse("admin/_swap_approvals_list.html", _pending_swaps_context(request, current_user, swap_service))
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response
