"""
Pydantic schemas for the SwapRequest resource.

Redesigned in Phase 3 (see ARCHITECTURE_ASSESSMENT.md section 3.2 and
IMPLEMENTATION_PROGRESS.md): a Swap exchanges one or more hardware field
values *between two setups* (business rule 5 -- both setups must contain
the selected field) and never relocates anyone's Reservation. The
multi-node swap-mapping schemas (``SwapMappingEntry`` /
``SwapMappingCreateRequest``) that powered reservation relocation have been
removed per business rule 6 ("remove/avoid swap-mapping functionality");
``SwapResponse.batch_id`` is kept, read-only, purely so historical
mapping-era rows still display correctly.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import AnnouncementChannel, SwapStatus


class SwapCreateRequest(BaseModel):
    """
    Payload for requesting a swap: exchange one or more hardware field
    values between two setups. Neither setup's Reservation is affected --
    this only ever changes the CURRENT/EFFECTIVE hardware field value(s) on
    each setup once approved.

    ``column_names`` accepts one or more column names to swap together in a
    single request. The legacy singular ``column_name`` is still accepted
    for backward compatibility (equivalent to ``column_names=[column_name]``)
    -- if both are omitted, every column common to the two setups is
    swapped (a full setup swap).

    ``announcement_channels`` mirrors ``ReservationCreateRequest``'s field
    of the same name/meaning. The setup's routed approvers (see
    ``ApprovalRoutingService``) are always notified by email regardless of
    ``announcement_channels`` -- that field controls the *additional*,
    broader-audience broadcast (dashboard Wall post, group, or everyone).
    """

    current_setup_id: int
    requested_setup_id: int
    column_name: Optional[str] = Field(default=None, max_length=100)
    column_names: Optional[List[str]] = Field(default=None)
    reason: Optional[str] = Field(default=None, max_length=500)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    announcement_channels: List[str] = Field(default_factory=list)
    announcement_message: Optional[str] = Field(default=None, max_length=2000)

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

    @validator("end_time")
    def _validate_window(cls, value: Optional[datetime], values: dict) -> Optional[datetime]:  # noqa: N805
        start_time = values.get("start_time")
        if value is not None and start_time is not None and value <= start_time:
            raise ValueError("end_time must be after start_time.")
        return value

    @validator("announcement_channels", each_item=True)
    def _validate_channel(cls, value: str) -> str:  # noqa: N805
        if value not in AnnouncementChannel.ALL:
            raise ValueError("announcement_channels entries must be one of: {0}".format(", ".join(AnnouncementChannel.ALL)))
        return value

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


class SwapResponse(BaseModel):
    """Read model for a SwapRequest."""

    id: int
    reservation_id: Optional[int] = None
    requester_id: int
    current_setup_id: Optional[int] = None
    requested_setup_id: Optional[int] = None
    column_name: Optional[str] = None
    column_names: List[str] = Field(default_factory=list)
    previous_current_value: Optional[str] = None
    previous_requested_value: Optional[str] = None
    status: str
    reason: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    announcement_channels: Optional[str] = None
    routed_approver_emails: Optional[str] = None
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
