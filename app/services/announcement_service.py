"""Announcement service: business logic for Announcement CRUD."""
from datetime import datetime
from typing import List, Tuple

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.models.announcement import Announcement
from app.models.user import User
from app.repositories.interfaces.i_announcement_repository import IAnnouncementRepository
from app.schemas.announcement import AnnouncementCreateRequest, AnnouncementFilter, AnnouncementUpdateRequest
from app.services.audit_service import AuditService


class AnnouncementService:
    """Business logic for Announcement CRUD and active-window filtering."""

    def __init__(self, announcement_repository: IAnnouncementRepository, audit_service: AuditService) -> None:
        self._announcement_repository = announcement_repository
        self._audit_service = audit_service

    def get_by_id(self, announcement_id: int) -> Announcement:
        announcement = self._announcement_repository.get_by_id(announcement_id)
        if announcement is None:
            raise NotFoundError("Announcement with id {0} was not found.".format(announcement_id))
        return announcement

    def list(self, filters: AnnouncementFilter, page: int, page_size: int) -> Tuple[List[Announcement], int]:
        return self._announcement_repository.list(filters, page, page_size, as_of=datetime.utcnow())

    def create(self, payload: AnnouncementCreateRequest, acting_user: User) -> Announcement:
        announcement = Announcement(
            title=payload.title,
            message=payload.message,
            created_by_id=acting_user.id,
            priority=payload.priority,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=True,
        )
        created = self._announcement_repository.create(announcement)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="Announcement",
            entity_id=created.id,
            new_value={"title": created.title, "priority": created.priority},
        )
        return created

    def update(self, announcement_id: int, payload: AnnouncementUpdateRequest, acting_user: User) -> Announcement:
        announcement = self.get_by_id(announcement_id)
        old_value = {"title": announcement.title, "is_active": announcement.is_active}

        update_data = payload.dict(exclude_unset=True)
        for field_name, field_value in update_data.items():
            setattr(announcement, field_name, field_value)

        updated = self._announcement_repository.update(announcement)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="Announcement",
            entity_id=updated.id,
            old_value=old_value,
            new_value={"title": updated.title, "is_active": updated.is_active},
        )
        return updated

    def delete(self, announcement_id: int, acting_user: User) -> None:
        self.get_by_id(announcement_id)
        self._announcement_repository.delete(announcement_id)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="Announcement",
            entity_id=announcement_id,
        )

    def sweep_expired(self, as_of: datetime) -> int:
        """Background-job entry point: flip expired announcements to inactive."""
        expired = self._announcement_repository.list_expired_active(as_of)
        for announcement in expired:
            announcement.is_active = False
            self._announcement_repository.update(announcement)
        return len(expired)
