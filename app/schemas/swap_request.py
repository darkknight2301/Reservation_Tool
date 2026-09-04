"""Pydantic schemas for the SwapRequest resource, including multi-node swap mappings."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import SwapStatus


class SwapCreateRequest(BaseModel):
    """
    Payload for requesting a swap: exchange one or more fields' values
    between two of the requester's own reserved setups.

    ``column_names`` accepts one or more column names to swap together in a
    single request. The legacy singular ``column_name`` is still accepted
    for backward compatibility (equivalent to ``column_names=[column_name]``)
    -- if both are omitted, every column common to the two setups is
    swapped (a full setup swap).
    """

    reservation_id: int
    requested_setup_id: int
    column_name: Optional[str] = Field(default=None, max_length=100)
    column_names: Optional[List[str]] = Field(default=None)
    reason: Optional[str] = Field(default=None, max_length=500)

    @validator("column_names")
    def _validate_column_names(cls, value: Optional[List[str]]) -> Optional[List[str]]:  # noqa: N805
        if value is None:
            return value
        cleaned = []
        for raw in value:
            name = (raw or "").strip()
            if not name:
                continue
            if len(name) > 100:
                raise ValueError("Each column name must be at most 100 characters.")
            if name not in cleaned:
                cleaned.append(name)
        if not cleaned:
            raise ValueError("column_names, if provided, must contain at least one non-empty column name.")
        return cleaned

    def resolved_column_names(self) -> Optional[List[str]]:
        """The effective list of requested column names, or None to mean 'every common column'."""
        if self.column_names:
            return self.column_names
        if self.column_name and self.column_name.strip():
            return [self.column_name.strip()]
        return None


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
    column_names: List[str] = Field(default_factory=list)
    previous_current_value: Optional[str] = None
    previous_requested_value: Optional[str] = None
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
