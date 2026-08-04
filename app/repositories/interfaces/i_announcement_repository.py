"""Repository interface (Protocol) for the Announcement aggregate."""
from datetime import datetime
from typing import List, Optional, Protocol, Tuple

from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementFilter


class IAnnouncementRepository(Protocol):
    """Persistence contract for Announcement entities."""

    def get_by_id(self, announcement_id: int) -> Optional[Announcement]:
        ...

    def list(self, filters: AnnouncementFilter, page: int, page_size: int, as_of: datetime) -> Tuple[List[Announcement], int]:
        ...

    def create(self, announcement: Announcement) -> Announcement:
        ...

    def update(self, announcement: Announcement) -> Announcement:
        ...

    def delete(self, announcement_id: int) -> None:
        ...

    def list_expired_active(self, as_of: datetime) -> List[Announcement]:
        ...
