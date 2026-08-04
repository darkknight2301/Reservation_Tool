"""Pydantic schemas for the SwapRequest resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import SwapStatus


class SwapCreateRequest(BaseModel):
    """Payload for requesting a swap of an active reservation's setup."""

    reservation_id: int
    requested_setup_id: int
    reason: Optional[str] = Field(default=None, max_length=500)


class SwapDecisionRequest(BaseModel):
    """Payload for approving or rejecting a pending swap request."""

    reason: Optional[str] = Field(default=None, max_length=500)


class SwapResponse(BaseModel):
    """Read model for a SwapRequest."""

    id: int
    reservation_id: int
    requester_id: int
    current_setup_id: int
    requested_setup_id: int
    status: str
    reason: Optional[str] = None
    approved_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class SwapFilter(BaseModel):
    """Query-parameter filter set for listing swap requests."""

    status: Optional[str] = None
    requester_id: Optional[int] = None

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in SwapStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(SwapStatus.ALL)))
        return value
