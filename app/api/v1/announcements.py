"""Announcement CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_announcement_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.announcement import (
    AnnouncementCreateRequest,
    AnnouncementFilter,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.announcement_service import AnnouncementService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/announcements", tags=["Announcements"])


@router.get("", response_model=PaginatedResponse[AnnouncementResponse])
def list_announcements(
    active_only: bool = False,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.ANNOUNCEMENT_VIEW)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
) -> PaginatedResponse:
    """List announcements. Requires ``announcement:view``."""
    filters = AnnouncementFilter(active_only=active_only, priority=priority)
    items, total_items = announcement_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=AnnouncementResponse, status_code=201)
def create_announcement(
    payload: AnnouncementCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Create an Announcement. Requires ``announcement:manage``."""
    return announcement_service.create(payload, current_user)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement(
    announcement_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.ANNOUNCEMENT_VIEW)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Fetch a single Announcement by id. Requires ``announcement:view``."""
    return announcement_service.get_by_id(announcement_id)


@router.patch("/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
):
    """Update an Announcement. Requires ``announcement:manage``."""
    return announcement_service.update(announcement_id, payload, current_user)


@router.delete("/{announcement_id}", response_model=MessageResponse)
def delete_announcement(
    announcement_id: int,
    current_user: User = Depends(require_permission(PermissionCode.ANNOUNCEMENT_MANAGE)),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
) -> MessageResponse:
    """Delete an Announcement. Requires ``announcement:manage``."""
    announcement_service.delete(announcement_id, current_user)
    return MessageResponse(message="Announcement deleted successfully.")
