"""SQLAlchemy implementation of the Announcement repository."""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.core.constants import AnnouncementPriority
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementFilter
from app.utils.pagination import paginate_query

_PRIORITY_RANK = case(
    (Announcement.priority == AnnouncementPriority.CRITICAL, 4),
    (Announcement.priority == AnnouncementPriority.HIGH, 3),
    (Announcement.priority == AnnouncementPriority.NORMAL, 2),
    (Announcement.priority == AnnouncementPriority.LOW, 1),
    else_=0,
)


class AnnouncementRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IAnnouncementRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, announcement_id: int) -> Optional[Announcement]:
        return self._db.query(Announcement).filter(Announcement.id == announcement_id).first()

    def list(
        self, filters: AnnouncementFilter, page: int, page_size: int, as_of: datetime
    ) -> Tuple[List[Announcement], int]:
        query = self._db.query(Announcement)
        if filters.priority:
            query = query.filter(Announcement.priority == filters.priority)
        if filters.active_only:
            query = query.filter(
                Announcement.is_active.is_(True),
                Announcement.start_date <= as_of,
                or_(Announcement.end_date.is_(None), Announcement.end_date >= as_of),
            )
        query = query.order_by(_PRIORITY_RANK.desc(), Announcement.created_at.desc())
        return paginate_query(query, page, page_size)

    def create(self, announcement: Announcement) -> Announcement:
        self._db.add(announcement)
        self._db.flush()
        self._db.refresh(announcement)
        return announcement

    def update(self, announcement: Announcement) -> Announcement:
        self._db.add(announcement)
        self._db.flush()
        self._db.refresh(announcement)
        return announcement

    def delete(self, announcement_id: int) -> None:
        announcement = self.get_by_id(announcement_id)
        if announcement is not None:
            self._db.delete(announcement)
            self._db.flush()

    def list_expired_active(self, as_of: datetime) -> List[Announcement]:
        return (
            self._db.query(Announcement)
            .filter(
                Announcement.is_active.is_(True),
                Announcement.end_date.isnot(None),
                Announcement.end_date < as_of,
            )
            .all()
        )
