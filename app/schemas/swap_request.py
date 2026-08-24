"""Pydantic schemas for the SwapRequest resource, including multi-node swap mappings."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import SwapStatus


class SwapCreateRequest(BaseModel):
    """Payload for requesting a swap: exchange one field's value between two of the requester's own reserved setups."""

    reservation_id: int
    requested_setup_id: int
    column_name: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)


class SwapDecisionRequest(BaseModel):
    """Payload for approving or rejecting a pending swap request."""

    reason: Optional[str] = Field(default=None, max_length=500)


class SwapMappingEntry(BaseModel):
    """One edge in a multi-node swap mapping: move this reservation to this setup."""

    reservation_id: int
    target_setup_id: int


class SwapMappingCreateRequest(BaseModel):
    """
    Payload for a coordinated multi-node swap mapping, e.g. A->B, B->A, C->D.

    Every ``reservation_id`` and every ``target_setup_id`` must appear
    exactly once across the whole mapping (see ``SwapService`` for the full
    validation rules); invalid mappings are rejected as a whole.
    """

    mappings: List[SwapMappingEntry] = Field(..., min_items=2)
    reason: Optional[str] = Field(default=None, max_length=500)

    @validator("mappings")
    def _validate_non_empty(cls, value: List[SwapMappingEntry]) -> List[SwapMappingEntry]:  # noqa: N805
        if len(value) < 2:
            raise ValueError("A swap mapping requires at least two entries.")
        return value


class SwapResponse(BaseModel):
    """Read model for a SwapRequest."""

    id: int
    reservation_id: int
    requester_id: int
    current_setup_id: int
    requested_setup_id: int
    column_name: Optional[str] = None
    status: str
    reason: Optional[str] = None
    batch_id: Optional[str] = None
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
