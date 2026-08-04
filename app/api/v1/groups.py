"""Group CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_group_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.group import GroupCreateRequest, GroupResponse, GroupUpdateRequest
from app.services.group_service import GroupService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("", response_model=PaginatedResponse[GroupResponse])
def list_groups(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.GROUP_VIEW)),
    group_service: GroupService = Depends(get_group_service),
) -> PaginatedResponse:
    """List groups. Requires ``group:view``."""
    items, total_items = group_service.list(page, page_size, search)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=GroupResponse, status_code=201)
def create_group(
    payload: GroupCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Create a Group. Requires ``group:manage``."""
    return group_service.create(payload, current_user)


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.GROUP_VIEW)),
    group_service: GroupService = Depends(get_group_service),
):
    """Fetch a single Group by id. Requires ``group:view``."""
    return group_service.get_by_id(group_id)


@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    payload: GroupUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
):
    """Update a Group. Requires ``group:manage``."""
    return group_service.update(group_id, payload, current_user)


@router.delete("/{group_id}", response_model=MessageResponse)
def delete_group(
    group_id: int,
    current_user: User = Depends(require_permission(PermissionCode.GROUP_MANAGE)),
    group_service: GroupService = Depends(get_group_service),
) -> MessageResponse:
    """Delete a Group. Requires ``group:manage``."""
    group_service.delete(group_id, current_user)
    return MessageResponse(message="Group deleted successfully.")
