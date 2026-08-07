"""Pydantic schemas for the Reservation resource."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import AnnouncementChannel, ReservationStatus


class ReservationCreateRequest(BaseModel):
    """
    Payload for creating a Reservation.

    ``announcement_channels`` lets the reserving user optionally broadcast
    the reservation: ``WALL`` posts a dashboard Announcement, ``MAIL_LEADS``
    / ``MAIL_GROUP`` / ``MAIL_ALL`` send email notifications scoped to the
    setup's Group. All are optional and may be combined.
    """

    setup_id: int
    reserved_from: datetime
    reserved_until: datetime
    remarks: Optional[str] = Field(default=None, max_length=2000)
    announcement_channels: List[str] = Field(default_factory=list)
    announcement_message: Optional[str] = Field(default=None, max_length=2000)

    @validator("reserved_until")
    def _validate_window(cls, value: datetime, values: dict) -> datetime:  # noqa: N805
        reserved_from = values.get("reserved_from")
        if reserved_from is not None and value <= reserved_from:
            raise ValueError("reserved_until must be after reserved_from.")
        return value

    @validator("announcement_channels", each_item=True)
    def _validate_channel(cls, value: str) -> str:  # noqa: N805
        if value not in AnnouncementChannel.ALL:
            raise ValueError("announcement_channels entries must be one of: {0}".format(", ".join(AnnouncementChannel.ALL)))
        return value


class ReservationResponse(BaseModel):
    """Read model for a Reservation."""

    id: int
    setup_id: int
    user_id: int
    reserved_from: datetime
    reserved_until: datetime
    status: str
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ReservationFilter(BaseModel):
    """Query-parameter filter set for listing reservations."""

    user_id: Optional[int] = None
    setup_id: Optional[int] = None
    status: Optional[str] = None
    reserved_from_after: Optional[datetime] = None
    reserved_until_before: Optional[datetime] = None

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in ReservationStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(ReservationStatus.ALL)))
        return value
