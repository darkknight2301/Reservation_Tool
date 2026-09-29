"""
Approvals screen (Phase 6): one place for Pending Approvals and Approval
History across Swap and Borrow.

Swap and Borrow stay independent domains -- this module only *lists* both side
by side and delegates every action to ``SwapService`` / ``BorrowService``
(which enforce the hierarchy routing). Buttons are shown only when the service
says the current user can actually act, so nobody is offered a dead action.
"""
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_borrow_service, get_swap_service
from app.core.constants import BorrowStatus, PermissionCode, SwapStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.borrow_request import BorrowDecisionRequest, BorrowFilter
from app.schemas.swap_request import SwapDecisionRequest, SwapFilter
from app.services.borrow_service import BorrowService
from app.services.swap_service import SwapService
from app.web.deps import base_context, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(prefix="/approvals", tags=["Web: Approvals"])

_SWAP_HISTORY = (SwapStatus.COMPLETED, SwapStatus.REJECTED, SwapStatus.CANCELLED, SwapStatus.EXPIRED)
_BORROW_HISTORY = (BorrowStatus.COMPLETED, BorrowStatus.RETURNED, BorrowStatus.REJECTED, BorrowStatus.CANCELLED, BorrowStatus.EXPIRED)


def _name(user) -> str:
    return user.full_name if user else "—"


def _swap_item(swap, user: User, swap_service: SwapService) -> Dict:
    a = swap.current_setup.hostname if swap.current_setup else "?"
    b = swap.requested_setup.hostname if swap.requested_setup else "?"
    return {
        "kind": "SWAP", "id": swap.id, "status": swap.status, "requester": _name(swap.requester),
        "title": "{0} ⇄ {1}".format(a, b), "detail": "Column(s): {0}".format(", ".join(swap.column_names) or "all common"),
        "reason": swap.reason, "start": swap.start_time, "end": swap.end_time, "routed": swap.routed_approver_emails,
        "decided_by": _name(swap.approved_by) if swap.approved_by_id else None, "created_at": swap.created_at,
        "updated_at": swap.updated_at,
        "can_decide": swap_service.can_decide(swap, user),
        "can_cancel": swap.status == SwapStatus.PENDING and swap.requester_id == user.id,
        "from_to": None,
    }


def _borrow_item(borrow, user: User, borrow_service: BorrowService) -> Dict:
    return {
        "kind": "BORROW", "id": borrow.id, "status": borrow.status, "requester": _name(borrow.requester),
        "title": "{0}{1}".format(borrow.setup.hostname if borrow.setup else "?", " ({0})".format(borrow.hardware_field_name) if borrow.hardware_field_name else " (entire setup)"),
        "detail": None, "reason": borrow.reason, "start": borrow.start_time, "end": borrow.end_time,
        "routed": borrow.routed_approver_emails,
        "decided_by": _name(borrow.approved_by) if borrow.approved_by_id else None, "created_at": borrow.created_at,
        "updated_at": borrow.updated_at,
        "can_decide": borrow_service.can_decide(borrow, user),
        "can_cancel": borrow.status == BorrowStatus.PENDING and borrow.requester_id == user.id,
        "from_to": "{0} (borrower) ← {1} (source)".format(
            borrow.target_group.name if borrow.target_group else "?", borrow.source_group.name if borrow.source_group else "?"
        ),
    }


def _context(request: Request, user: User, swap_service: SwapService, borrow_service: BorrowService, tab: str, mine: bool) -> dict:
    perms = base_context(request, user)["current_user_permissions"]
    show_borrow = PermissionCode.BORROW_VIEW in perms
    swap_filter = dict(requester_id=user.id) if mine else {}
    statuses_swap = (SwapStatus.PENDING,) if tab == "pending" else _SWAP_HISTORY
    statuses_borrow = (BorrowStatus.PENDING,) if tab == "pending" else _BORROW_HISTORY

    items: List[Dict] = []
    for status in statuses_swap:
        found, _ = swap_service.list(SwapFilter(status=status, **swap_filter), page=1, page_size=200)
        items.extend(_swap_item(s, user, swap_service) for s in found)
    if show_borrow:
        for status in statuses_borrow:
            found, _ = borrow_service.list(BorrowFilter(status=status, **swap_filter), page=1, page_size=200)
            items.extend(_borrow_item(b, user, borrow_service) for b in found)
    items.sort(key=lambda i: (i["updated_at"], i["id"]), reverse=True)

    context = base_context(request, user)
    context.update({"items": items[:200], "tab": tab, "mine": mine, "show_borrow": show_borrow, "now": datetime.utcnow()})
    return context


@router.get("")
def approvals_page(
    request: Request,
    tab: str = "pending",
    mine: bool = False,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_VIEW)),
    swap_service: SwapService = Depends(get_swap_service),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Render the Approvals screen (Pending Approvals / Approval History)."""
    tab = tab if tab in ("pending", "history") else "pending"
    return templates.TemplateResponse("approvals/approvals.html", _context(request, current_user, swap_service, borrow_service, tab, mine))


@router.get("/content")
def approvals_content(
    request: Request,
    tab: str = "pending",
    mine: bool = False,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_VIEW)),
    swap_service: SwapService = Depends(get_swap_service),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """HTMX partial: tab / filter switch."""
    tab = tab if tab in ("pending", "history") else "pending"
    return templates.TemplateResponse("approvals/_content.html", _context(request, current_user, swap_service, borrow_service, tab, mine))


def _act(request, user, swap_service, borrow_service, action, ok_message, tab="pending", mine=False):
    message, message_type = ok_message, "success"
    try:
        action()
    except AppError as exc:
        message, message_type = exc.message, "error"
    response = templates.TemplateResponse("approvals/_content.html", _context(request, user, swap_service, borrow_service, tab, mine))
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/swap/{swap_id}/approve")
def approve_swap(
    request: Request, swap_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service,
                lambda: swap_service.approve(swap_id, SwapDecisionRequest(), current_user), "Swap approved -- values have been exchanged.")


@router.post("/swap/{swap_id}/reject")
def reject_swap(
    request: Request, swap_id: int, rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service,
                lambda: swap_service.reject(swap_id, SwapDecisionRequest(reason=rejection_reason or None), current_user), "Swap request rejected.")


@router.post("/swap/{swap_id}/cancel")
def cancel_swap(
    request: Request, swap_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_VIEW)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service, lambda: swap_service.cancel(swap_id, current_user), "Swap request cancelled.")


@router.post("/borrow/{borrow_id}/approve")
def approve_borrow(
    request: Request, borrow_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service,
                lambda: borrow_service.approve(borrow_id, BorrowDecisionRequest(), current_user),
                "Borrow approved -- access has been granted to the borrowing group.")


@router.post("/borrow/{borrow_id}/reject")
def reject_borrow(
    request: Request, borrow_id: int, rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_APPROVE)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service,
                lambda: borrow_service.reject(borrow_id, BorrowDecisionRequest(reason=rejection_reason or None), current_user),
                "Borrow request rejected.")


@router.post("/borrow/{borrow_id}/cancel")
def cancel_borrow(
    request: Request, borrow_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_VIEW)),
    swap_service: SwapService = Depends(get_swap_service), borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, swap_service, borrow_service, lambda: borrow_service.cancel(borrow_id, current_user), "Borrow request cancelled.")
