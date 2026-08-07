"""Announcement Manager screen: list active announcements, CRUD for permitted roles."""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_announcement_service
from app.core.constants import AnnouncementPriority, PermissionCode
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.announcement import AnnouncementCreateRequest, AnnouncementFilter, AnnouncementUpdateRequest
from app.services.announcement_service import AnnouncementService
from app.web.deps import base_context, get_current_web_user, require_web_permission, templates

router = APIRouter(tags=["Web - Announcements"])


@router.get("/announcements")
def announcements_page(
    request: Request,
    current_user: User = Depends(get_current_web_user),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Render the full Announcement Manager screen."""
    announcements, total_items = announcement_service.list(AnnouncementFilter(), page=1, page_size=50)
    context = base_context(request, current_user)
    context.update({"announcements": announcements, "priorities": AnnouncementPriority.ALL})
    return templates.TemplateResponse("announcements/manager.html", context)


@router.get("/announcements/list")
def announcements_list_partial(
    request: Request,
    active_only: bool = False,
    current_user: User = Depends(get_current_web_user),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """HTMX partial: re-render the announcement list."""
    announcements, _ = announcement_service.list(AnnouncementFilter(active_only=active_only), page=1, page_size=50)
    context = base_context(request, current_user)
    context.update({"announcements": announcements})
    return templates.TemplateResponse("announcements/_list.html", context)


@router.get("/announcements/form")
def announcement_form_dialog(
    request: Request,
    announcement_id: Optional[int] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Render the create/edit Announcement modal."""
    announcement = announcement_service.get_by_id(announcement_id) if announcement_id else None
    context = base_context(request, current_user)
    context.update({"announcement": announcement, "priorities": AnnouncementPriority.ALL})
    return templates.TemplateResponse("announcements/_form_modal.html", context)


@router.post("/announcements/save")
def announcement_save(
    request: Request,
    announcement_id: Optional[str] = Form(default=""),
    title: str = Form(...),
    message: str = Form(...),
    priority: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Create or update an Announcement, then re-render the list."""
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    try:
        if announcement_id:
            payload = AnnouncementUpdateRequest(title=title, message=message, priority=priority, start_date=start_dt, end_date=end_dt)
            announcement_service.update(int(announcement_id), payload, current_user)
            toast_message = "Announcement updated successfully."
        else:
            payload = AnnouncementCreateRequest(title=title, message=message, priority=priority, start_date=start_dt, end_date=end_dt)
            announcement_service.create(payload, current_user)
            toast_message = "Announcement created successfully."
    except AppError as exc:
        toast_message = exc.message

    announcements, _ = announcement_service.list(AnnouncementFilter(), page=1, page_size=50)
    context = base_context(request, current_user)
    context.update({"announcements": announcements})
    response = templates.TemplateResponse("announcements/_list.html", context)
    response.headers["HX-Trigger"] = _toast_and_close(toast_message)
    return response


@router.delete("/announcements/{announcement_id}")
def announcement_delete(
    request: Request,
    announcement_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Delete an Announcement, then re-render the list."""
    announcement_service.delete(announcement_id, current_user)
    announcements, _ = announcement_service.list(AnnouncementFilter(), page=1, page_size=50)
    context = base_context(request, current_user)
    context.update({"announcements": announcements})
    response = templates.TemplateResponse("announcements/_list.html", context)
    response.headers["HX-Trigger"] = _toast_only("Announcement deleted successfully.")
    return response


def _toast_and_close(message: str) -> str:
    return json.dumps({"showToast": {"message": message, "type": "success"}, "closeDialog": {}})


def _toast_only(message: str) -> str:
    return json.dumps({"showToast": {"message": message, "type": "success"}})
