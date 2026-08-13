"""Group Management admin screen: list/create/update/delete Groups."""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_group_service
from app.core.constants import PermissionCode
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.group import GroupCreateRequest, GroupUpdateRequest
from app.services.group_service import GroupService
from app.web.deps import base_context, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(tags=["Web - Groups"])


@router.get("/admin/groups")
def group_management_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Render the Group Management admin screen."""
    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"groups": groups})
    return templates.TemplateResponse("admin/groups.html", context)


@router.get("/admin/groups/list")
def group_list_partial(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """HTMX partial: re-render the Group list table."""
    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"groups": groups})
    return templates.TemplateResponse("admin/_groups_list.html", context)


@router.get("/admin/groups/form")
def group_form_dialog(
    request: Request,
    group_id: Optional[int] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Render the create/edit Group modal."""
    group = group_service.get_by_id(group_id) if group_id else None
    context = base_context(request, current_user)
    context.update({"group": group})
    return templates.TemplateResponse("admin/_group_form_modal.html", context)


@router.post("/admin/groups/save")
def group_save(
    request: Request,
    group_id: str = Form(default=""),
    name: str = Form(...),
    description: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Create or update a Group, then re-render the list."""
    message, message_type = "Group saved successfully.", "success"
    try:
        if group_id:
            group_service.update(int(group_id), GroupUpdateRequest(name=name, description=description or None), current_user)
        else:
            group_service.create(GroupCreateRequest(name=name, description=description or None), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"groups": groups})
    response = templates.TemplateResponse("admin/_groups_list.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=(message_type == "success"))
    return response


@router.delete("/admin/groups/{group_id}")
def group_delete(
    request: Request,
    group_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Delete a Group, then re-render the list."""
    message, message_type = "Group deleted successfully.", "success"
    try:
        group_service.delete(group_id, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"groups": groups})
    response = templates.TemplateResponse("admin/_groups_list.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response
