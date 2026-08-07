"""User Management admin screen and the Approval Dashboard."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_group_service, get_user_service
from app.core.constants import PermissionCode, RoleName, UserStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.user import (
    UserApprovalRequest,
    UserCreateRequest,
    UserFilter,
    UserUpdateRequest,
)
from app.services.group_service import GroupService
from app.services.user_service import UserService
from app.web.deps import base_context, require_web_permission, templates

router = APIRouter(tags=["Web - Users"])


@router.get("/admin/users")
def user_management_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
    group_service: GroupService = Depends(get_group_service),
):
    """Render the User Management admin screen."""
    users, total_items = user_service.list(UserFilter(), page=1, page_size=100)
    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"users": users, "groups": groups, "roles": RoleName.ALL})
    return templates.TemplateResponse("admin/users.html", context)


@router.get("/admin/users/list")
def user_list_partial(
    request: Request,
    status: Optional[str] = None,
    role_name: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
):
    """HTMX partial: re-render the User list table."""
    users, _ = user_service.list(UserFilter(status=status, role_name=role_name, search=search), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"users": users})
    return templates.TemplateResponse("admin/_users_list.html", context)


@router.get("/admin/users/form")
def user_form_dialog(
    request: Request,
    user_id: Optional[int] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
    group_service: GroupService = Depends(get_group_service),
):
    """Render the create/edit User modal."""
    edited_user = user_service.get_by_id(user_id) if user_id else None
    groups, _ = group_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"edited_user": edited_user, "groups": groups, "roles": RoleName.ALL})
    return templates.TemplateResponse("admin/_user_form_modal.html", context)


@router.post("/admin/users/save")
def user_save(
    request: Request,
    user_id: str = Form(default=""),
    username: str = Form(default=""),
    email: str = Form(default=""),
    password: str = Form(default=""),
    full_name: str = Form(...),
    role_name: str = Form(...),
    group_id: str = Form(default=""),
    is_active: Optional[str] = Form(default=None),
    current_user: User = Depends(require_web_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
):
    """Create or update a User, then re-render the list."""
    message = "User saved successfully."
    resolved_group_id = int(group_id) if group_id else None
    try:
        if user_id:
            payload = UserUpdateRequest(
                full_name=full_name, role_name=role_name, group_id=resolved_group_id, is_active=bool(is_active)
            )
            user_service.update(int(user_id), payload, current_user)
        else:
            payload = UserCreateRequest(
                username=username, email=email, password=password, full_name=full_name,
                role_name=role_name, group_id=resolved_group_id,
            )
            user_service.create(payload, current_user)
    except AppError as exc:
        message = exc.message
    except ValueError as exc:
        message = str(exc)

    users, _ = user_service.list(UserFilter(), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"users": users})
    response = templates.TemplateResponse("admin/_users_list.html", context)
    response.headers["HX-Trigger"] = json.dumps({"showToast": {"message": message, "type": "success"}, "closeDialog": {}})
    return response


@router.delete("/admin/users/{user_id}")
def user_delete(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
):
    """Deactivate a User, then re-render the list."""
    message, message_type = "User deactivated successfully.", "success"
    try:
        user_service.delete(user_id, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    users, _ = user_service.list(UserFilter(), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"users": users})
    response = templates.TemplateResponse("admin/_users_list.html", context)
    response.headers["HX-Trigger"] = json.dumps({"showToast": {"message": message, "type": message_type}})
    return response


# ------------------------------------------------------------------------
# Approval Dashboard
# ------------------------------------------------------------------------

@router.get("/admin/approvals")
def approval_dashboard_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_APPROVE)),
    user_service: UserService = Depends(get_user_service),
):
    """Render the Approval Dashboard: users awaiting approval."""
    pending_users, _ = user_service.list(UserFilter(status=UserStatus.PENDING), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"pending_users": pending_users, "roles": RoleName.ALL})
    return templates.TemplateResponse("admin/approvals.html", context)


@router.get("/admin/approvals/list")
def approval_list_partial(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.USER_APPROVE)),
    user_service: UserService = Depends(get_user_service),
):
    """HTMX partial: re-render the pending-approval list."""
    pending_users, _ = user_service.list(UserFilter(status=UserStatus.PENDING), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"pending_users": pending_users, "roles": RoleName.ALL})
    return templates.TemplateResponse("admin/_approvals_list.html", context)


@router.post("/admin/approvals/{user_id}")
def process_approval(
    request: Request,
    user_id: int,
    approve: str = Form(...),
    role_name: str = Form(default=""),
    rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.USER_APPROVE)),
    user_service: UserService = Depends(get_user_service),
):
    """Approve or reject a pending registration, then re-render the list."""
    message, message_type = "Approval processed successfully.", "success"
    try:
        payload = UserApprovalRequest(
            approve=(approve == "true"), role_name=role_name or None, rejection_reason=rejection_reason or None
        )
        user_service.process_approval(user_id, payload, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    pending_users, _ = user_service.list(UserFilter(status=UserStatus.PENDING), page=1, page_size=100)
    context = base_context(request, current_user)
    context.update({"pending_users": pending_users, "roles": RoleName.ALL})
    response = templates.TemplateResponse("admin/_approvals_list.html", context)
    response.headers["HX-Trigger"] = json.dumps({"showToast": {"message": message, "type": message_type}})
    return response
