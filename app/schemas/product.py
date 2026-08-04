"""Pydantic schemas for the Product resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductCreateRequest(BaseModel):
    """Payload for creating a Product."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class ProductUpdateRequest(BaseModel):
    """Payload for updating a Product. All fields optional."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class ProductResponse(BaseModel):
    """Read model for a Product."""

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
