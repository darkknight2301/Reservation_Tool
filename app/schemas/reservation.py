"""Pydantic schemas for the Reservation resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import ReservationStatus


class ReservationCreateRequest(BaseModel):
    """Payload for creating a Reservation."""

    setup_id: int
    reserved_from: datetime
    reserved_until: datetime
    purpose: Optional[str] = Field(default=None, max_length=500)

    @validator("reserved_until")
    def _validate_window(cls, value: datetime, values: dict) -> datetime:  # noqa: N805
        reserved_from = values.get("reserved_from")
        if reserved_from is not None and value <= reserved_from:
            raise ValueError("reserved_until must be after reserved_from.")
        return value


class ReservationResponse(BaseModel):
    """Read model for a Reservation."""

    id: int
    setup_id: int
    user_id: int
    reserved_from: datetime
    reserved_until: datetime
    status: str
    purpose: Optional[str] = None
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
