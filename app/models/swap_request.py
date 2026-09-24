"""SwapRequest ORM model."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.constants import SwapStatus
from app.db.base import Base


class SwapRequest(Base):
    """
    A request to change one or more hardware field values.

    Historical rows (created before the Phase 1 data-model revision) used
    this table to relocate the requester's Reservation to a different setup
    -- see ARCHITECTURE_ASSESSMENT.md section 3.2. That behavior is being
    retired in Phase 3: going forward a Swap changes CURRENT/EFFECTIVE
    hardware fields on a *single* Setup (``setup_id`` below) and never
    creates or relocates a Reservation. The legacy ``current_setup_id`` /
    ``requested_setup_id`` / ``reservation_id`` columns are kept, unmodified,
    so existing completed-swap history stays exactly as it was recorded;
    new rows populate ``setup_id`` (and leave the relocation-shaped columns
    NULL) instead.
    """

    __tablename__ = "swap_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Legacy relocation-flow columns. Nullable (widened from NOT NULL by the
    # Phase 1 migration) because new-style, non-relocating Swap requests
    # populate ``setup_id`` instead and leave these NULL; existing rows keep
    # their original, non-NULL values untouched.
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=True)
    requested_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=True)

    # New-style single-setup hardware change target. Exactly one of
    # (setup_id) or (current_setup_id + requested_setup_id) is populated on
    # any given row, depending on whether it predates this revision.
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=True, index=True)

    # Business rule: "Reserve/Swap/Borrow should support reason, start time,
    # end time, announcement and applicable lead emails." ``reason`` already
    # existed below; these three are additive.
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    announcement_channels = Column(String(200), nullable=True)  # comma-separated AnnouncementChannel values

    # Snapshot of who this request was routed to at creation time
    # (comma-separated emails), resolved via the data-driven approval
    # hierarchy -- see BorrowRequest.routed_approver_emails for the same
    # pattern and rationale.
    routed_approver_emails = Column(Text, nullable=True)

    # The field(s) being exchanged between current_setup and requested_setup:
    # a comma-separated list of one or more fixed Setup column names (e.g.
    # "ssd,hdd") and/or custom template column names, each common to both
    # setups' products when they differ. Widened from 100 -> 500 chars (see
    # alembic 0009) to comfortably hold several column names at once.
    column_name = Column(String(500), nullable=True)

    # Captured at approval time, before the exchange -- lets anyone with
    # ``swap:view`` (every role) see what each setup's value was before the
    # swap, so it can be restored later (e.g. via Setup Edit) if needed.
    previous_current_value = Column(String(500), nullable=True)
    previous_requested_value = Column(String(500), nullable=True)

    status = Column(String(20), nullable=False, default=SwapStatus.PENDING, index=True)
    reason = Column(String(500), nullable=True)
    batch_id = Column(String(36), nullable=True, index=True)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    reservation = relationship("Reservation", foreign_keys=[reservation_id])
    requester = relationship("User", foreign_keys=[requester_id])
    current_setup = relationship("Setup", foreign_keys=[current_setup_id])
    requested_setup = relationship("Setup", foreign_keys=[requested_setup_id])
    setup = relationship("Setup", foreign_keys=[setup_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SwapRequest id={0} status={1}>".format(self.id, self.status)

    @property
    def column_names(self):  # type: () -> list
        """The swapped column name(s) as a list, parsed from the stored comma-separated string."""
        if not self.column_name:
            return []
        return [part.strip() for part in self.column_name.split(",") if part.strip()]
