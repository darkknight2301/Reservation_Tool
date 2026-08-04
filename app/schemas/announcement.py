"""Pydantic schemas for the Announcement resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import AnnouncementPriority


class AnnouncementCreateRequest(BaseModel):
    """Payload for creating an Announcement."""

    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field(default=AnnouncementPriority.NORMAL)
    start_date: datetime
    end_date: Optional[datetime] = None

    @validator("priority")
    def _validate_priority(cls, value: str) -> str:  # noqa: N805
        if value not in AnnouncementPriority.ALL:
            raise ValueError("priority must be one of: {0}".format(", ".join(AnnouncementPriority.ALL)))
        return value

    @validator("end_date")
    def _validate_window(cls, value: Optional[datetime], values: dict) -> Optional[datetime]:  # noqa: N805
        start_date = values.get("start_date")
        if value is not None and start_date is not None and value <= start_date:
            raise ValueError("end_date must be after start_date.")
        return value


class AnnouncementUpdateRequest(BaseModel):
    """Payload for updating an Announcement. All fields optional."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    message: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    priority: Optional[str] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @validator("priority")
    def _validate_priority(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in AnnouncementPriority.ALL:
            raise ValueError("priority must be one of: {0}".format(", ".join(AnnouncementPriority.ALL)))
        return value


class AnnouncementResponse(BaseModel):
    """Read model for an Announcement."""

    id: int
    title: str
    message: str
    created_by_id: int
    priority: str
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class AnnouncementFilter(BaseModel):
    """Query-parameter filter set for listing announcements."""

    active_only: bool = False
    priority: Optional[str] = None
