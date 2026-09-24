"""
BorrowRequest ORM model.

Represents a temporary transfer of setup/hardware access from one Group
(the source) to another (the borrower's group), raised by a Lead or Manager
of the borrowing group against a Lead/Manager of the source group -- an
independent transaction domain from Reservation and Swap (see
ARCHITECTURE_ASSESSMENT.md section 10). Borrow never relocates a
Reservation and never itself changes a setup's ORIGINAL owning group
(``Setup.group_id``); an approved Borrow instead creates a
``SetupAccessGrant`` row representing the temporary effective access, which
Return later closes out. Preserved history: this row (and its
``HardwareChangeLog`` entries, when the borrow also changes a specific
hardware field's effective value) remain queryable after Return -- nothing
is deleted.

Supports both whole-setup borrowing (``hardware_field_name`` is ``NULL``)
and single-hardware-field borrowing (``hardware_field_name`` set to one of
``app.services.swap_service.SWAPPABLE_SETUP_FIELDS``) -- see
ARCHITECTURE_ASSESSMENT.md, Open Question 5; both are supported at the
schema level so the decision of which to expose in the UI/service layer
does not require another migration.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.constants import BorrowStatus
from app.db.base import Base


class BorrowRequest(Base):
    """A request to temporarily transfer setup/hardware access across groups."""

    __tablename__ = "borrow_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    target_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)

    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    # NULL = borrowing the whole setup; otherwise one of SWAPPABLE_SETUP_FIELDS
    # naming the single hardware field being borrowed.
    hardware_field_name = Column(String(100), nullable=True)

    reason = Column(String(500), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    announcement_channels = Column(String(200), nullable=True)  # comma-separated, mirrors SwapRequest

    status = Column(String(20), nullable=False, default=BorrowStatus.PENDING, index=True)

    # Snapshot of who the request was routed to at creation time (comma-
    # separated emails), resolved via the data-driven approval hierarchy --
    # kept even after approval/rejection so "who could have approved this"
    # is answerable without re-walking a hierarchy that may since have
    # changed. Approval itself only requires ANY ONE of these to act.
    routed_approver_emails = Column(Text, nullable=True)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    returned_at = Column(DateTime, nullable=True)
    returned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    requester = relationship("User", foreign_keys=[requester_id])
    source_group = relationship("Group", foreign_keys=[source_group_id])
    target_group = relationship("Group", foreign_keys=[target_group_id])
    setup = relationship("Setup", foreign_keys=[setup_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    returned_by = relationship("User", foreign_keys=[returned_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<BorrowRequest id={0} status={1}>".format(self.id, self.status)
