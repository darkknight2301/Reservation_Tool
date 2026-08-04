"""Pydantic schemas for the Group resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GroupCreateRequest(BaseModel):
    """Payload for creating a Group."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class GroupUpdateRequest(BaseModel):
    """Payload for updating a Group. All fields optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class GroupResponse(BaseModel):
    """Read model for a Group."""

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
