"""Announcement ORM model."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import AnnouncementPriority
from app.db.base import Base


class Announcement(Base):
    """An admin-authored broadcast message shown on the dashboard."""

    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    message = Column(String(2000), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    priority = Column(String(20), nullable=False, default=AnnouncementPriority.NORMAL)
    is_active = Column(Boolean, nullable=False, default=True)

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Announcement id={0} title={1}>".format(self.id, self.title)
