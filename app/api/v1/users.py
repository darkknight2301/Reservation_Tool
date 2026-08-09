"""User management endpoints, including the registration approval workflow."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import (
    UserApprovalRequest,
    UserCreateRequest,
    UserFilter,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user


@router.get("", response_model=PaginatedResponse[UserResponse])
def list_users(
    status: Optional[str] = None,
    role_name: Optional[str] = None,
    group_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.USER_VIEW)),
    user_service: UserService = Depends(get_user_service),
) -> PaginatedResponse:
    """List users with optional filters. Requires ``user:view``."""
    filters = UserFilter(status=status, role_name=role_name, group_id=group_id, search=search)
    items, total_items = user_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Directly create an already-approved user. Requires ``user:manage``."""
    return user_service.create(payload, current_user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.USER_VIEW)),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Fetch a single user by id. Requires ``user:view``."""
    return user_service.get_by_id(user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Update a user's profile/role/group. Requires ``user:manage``."""
    return user_service.update(user_id, payload, current_user)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """Soft-delete (deactivate) a user. Requires ``user:manage``."""
    user_service.delete(user_id, current_user)
    return MessageResponse(message="User deactivated successfully.")


@router.delete("/{user_id}/permanent", response_model=MessageResponse)
def hard_delete_user(
    user_id: int,
    current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
) -> MessageResponse:
    """
    Permanently delete a user. Requires ``user:manage``. Fails with 409 if
    the user still has dependent records (reservations, swaps,
    announcements, exports) -- deactivate instead in that case.
    """
    user_service.hard_delete(user_id, current_user)
    return MessageResponse(message="User permanently deleted.")


@router.post("/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: int,
    current_user: User = Depends(require_permission(PermissionCode.USER_MANAGE)),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Reactivate a disabled/rejected user. Requires ``user:manage``."""
    return user_service.reactivate(user_id, current_user)


@router.post("/{user_id}/approval", response_model=UserResponse)
def process_user_approval(
    user_id: int,
    payload: UserApprovalRequest,
    current_user: User = Depends(require_permission(PermissionCode.USER_APPROVE)),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Approve or reject a pending registration. Requires ``user:approve``."""
    return user_service.process_approval(user_id, payload, current_user)
