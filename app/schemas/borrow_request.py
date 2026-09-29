"""
Pydantic schemas for the BorrowRequest resource (Phase 5).

A Borrow is raised by a Lead/Manager who selects the *source lead* whose
setup/hardware they need; approval is routed by the Borrow-specific
hierarchy (``ApprovalRoutingService.resolve_borrow_approvers``). It is an
independent domain from Reservation and Swap.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import AnnouncementChannel, BorrowStatus


class BorrowCreateRequest(BaseModel):
    """
    Payload for requesting a Borrow.

    ``source_lead_id`` is the Lead/Manager whose group's setup is needed;
    ``setup_id`` must belong to a group that lead belongs to.
    ``hardware_field_name`` is optional: omit it to borrow the whole setup,
    or name the one hardware field (fixed or custom template column) that
    is actually required.
    """

    source_lead_id: int
    setup_id: int
    hardware_field_name: Optional[str] = Field(default=None, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    announcement_channels: List[str] = Field(default_factory=list)
    announcement_message: Optional[str] = Field(default=None, max_length=2000)

    @validator("hardware_field_name")
    def _blank_field_is_none(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

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


class BorrowDecisionRequest(BaseModel):
    """Payload for approving or rejecting a pending borrow request (the note is recorded in the audit log)."""

    reason: Optional[str] = Field(default=None, max_length=500)


class BorrowReturnRequest(BaseModel):
    """Payload for returning a borrowed setup/hardware (the note is recorded in the audit log and the return notification)."""

    note: Optional[str] = Field(default=None, max_length=500)


class BorrowResponse(BaseModel):
    """Read model for a BorrowRequest."""

    id: int
    requester_id: int
    source_group_id: int
    target_group_id: int
    setup_id: int
    hardware_field_name: Optional[str] = None
    reason: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    announcement_channels: Optional[str] = None
    status: str
    routed_approver_emails: Optional[str] = None
    approved_by_id: Optional[int] = None
    returned_at: Optional[datetime] = None
    returned_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class BorrowFilter(BaseModel):
    """Query-parameter filter set for listing borrow requests."""

    status: Optional[str] = None
    requester_id: Optional[int] = None
    setup_id: Optional[int] = None
    group_id: Optional[int] = None  # matches either the source (lending) or borrowing group

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in BorrowStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(BorrowStatus.ALL)))
        return value
