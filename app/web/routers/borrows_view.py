"""
Borrow screen (Phase 5): request a borrow from another group's lead, approve/
reject routed requests, and return ("get back") borrowed setups.

Independent from the Reservation table and the Swap dialogs. All decisions go
through ``BorrowService`` -- this module only renders and calls it.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError

from app.api.deps import get_borrow_service, get_user_service
from app.core.constants import AnnouncementChannel, BorrowStatus, PermissionCode
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.borrow_request import BorrowCreateRequest, BorrowDecisionRequest, BorrowFilter, BorrowReturnRequest
from app.services.borrow_service import BorrowService
from app.services.user_service import UserService
from app.web.deps import base_context, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(prefix="/borrows", tags=["Web: Borrows"])


def _lists_context(request: Request, current_user: User, borrow_service: BorrowService) -> dict:
    pending, _ = borrow_service.list(BorrowFilter(status=BorrowStatus.PENDING), page=1, page_size=200)
    active, _ = borrow_service.list(BorrowFilter(status=BorrowStatus.COMPLETED), page=1, page_size=200)
    history = []
    for status in (BorrowStatus.RETURNED, BorrowStatus.REJECTED, BorrowStatus.CANCELLED, BorrowStatus.EXPIRED):
        items, _ = borrow_service.list(BorrowFilter(status=status), page=1, page_size=100)
        history.extend(items)
    history.sort(key=lambda b: (b.updated_at, b.id), reverse=True)
    context = base_context(request, current_user)
    context.update({"pending": pending, "active": active, "history": history[:100], "now": datetime.utcnow()})
    return context


def _respond(request, current_user, borrow_service, message, message_type, close_dialog=False):
    response = templates.TemplateResponse("borrows/_lists.html", _lists_context(request, current_user, borrow_service))
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=close_dialog)
    return response


@router.get("")
def borrows_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_VIEW)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Render the Borrow screen: pending requests, currently borrowed setups (with Return), and history."""
    return templates.TemplateResponse("borrows/borrows.html", _lists_context(request, current_user, borrow_service))


@router.get("/request-dialog")
def request_dialog(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_REQUEST)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Borrow request dialog: pick the source lead first; the setup list follows from that choice."""
    context = base_context(request, current_user)
    context.update({"source_leads": borrow_service.list_source_leads(current_user), "announcement_channels": AnnouncementChannel.ALL})
    return templates.TemplateResponse("borrows/request_dialog.html", context)


@router.get("/request-dialog/setups")
def request_dialog_setups(
    request: Request,
    source_lead_id: Optional[str] = None,
    setup_id: Optional[str] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_REQUEST)),
    borrow_service: BorrowService = Depends(get_borrow_service),
    user_service: UserService = Depends(get_user_service),
):
    """HTMX partial: setups belonging to the selected lead's group(s), and the hardware choices for the chosen setup."""
    setups, fields, selected = [], [], None
    if source_lead_id:
        lead = user_service.get_by_id(int(source_lead_id))
        setups = borrow_service.list_borrowable_setups(lead, current_user)
        selected = next((s for s in setups if setup_id and s.id == int(setup_id)), setups[0] if setups else None)
        fields = borrow_service.borrowable_fields(selected) if selected else []
    context = base_context(request, current_user)
    context.update({"setups": setups, "selected_setup": selected, "hardware_fields": fields, "source_lead_id": source_lead_id})
    return templates.TemplateResponse("borrows/_setup_fields.html", context)


@router.post("/request")
def request_submit(
    request: Request,
    source_lead_id: int = Form(...),
    setup_id: int = Form(...),
    hardware_field_name: str = Form(default=""),
    reason: str = Form(default=""),
    start_time: str = Form(default=""),
    end_time: str = Form(default=""),
    announcement_channels: List[str] = Form(default=[]),
    announcement_message: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_REQUEST)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    """Submit a borrow request for approval."""
    message, message_type = "Borrow request submitted for approval.", "success"
    try:
        borrow_service.create(
            BorrowCreateRequest(
                source_lead_id=source_lead_id, setup_id=setup_id, hardware_field_name=hardware_field_name or None,
                reason=reason or None,
                start_time=datetime.fromisoformat(start_time) if start_time else None,
                end_time=datetime.fromisoformat(end_time) if end_time else None,
                announcement_channels=announcement_channels, announcement_message=announcement_message or None,
            ),
            current_user,
        )
    except AppError as exc:
        message, message_type = exc.message, "error"
    except (ValidationError, ValueError) as exc:
        message = "; ".join(err["msg"] for err in exc.errors()) if isinstance(exc, ValidationError) else str(exc)
        message_type = "error"
    return _respond(request, current_user, borrow_service, message, message_type, close_dialog=(message_type == "success"))


def _act(request, current_user, borrow_service, action, ok_message):
    message, message_type = ok_message, "success"
    try:
        action()
    except AppError as exc:
        message, message_type = exc.message, "error"
    return _respond(request, current_user, borrow_service, message, message_type)


@router.post("/{borrow_id}/approve")
def approve_borrow_web(
    request: Request, borrow_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_APPROVE)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, borrow_service,
                lambda: borrow_service.approve(borrow_id, BorrowDecisionRequest(), current_user),
                "Borrow approved -- access has been granted to the borrowing group.")


@router.post("/{borrow_id}/reject")
def reject_borrow_web(
    request: Request, borrow_id: int, rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_APPROVE)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, borrow_service,
                lambda: borrow_service.reject(borrow_id, BorrowDecisionRequest(reason=rejection_reason or None), current_user),
                "Borrow request rejected.")


@router.post("/{borrow_id}/cancel")
def cancel_borrow_web(
    request: Request, borrow_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_VIEW)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, borrow_service,
                lambda: borrow_service.cancel(borrow_id, current_user), "Borrow request cancelled.")


@router.post("/{borrow_id}/return")
def return_borrow_web(
    request: Request, borrow_id: int, note: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.BORROW_RETURN)),
    borrow_service: BorrowService = Depends(get_borrow_service),
):
    return _act(request, current_user, borrow_service,
                lambda: borrow_service.return_borrow(borrow_id, BorrowReturnRequest(note=note or None), current_user),
                "Returned -- access has been restored to the source group and the leads were notified.")
