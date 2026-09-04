"""SwapRequest ORM model."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import SwapStatus
from app.db.base import Base


class SwapRequest(Base):
    """
    A request to exchange one field's recorded value (e.g. an SSD) between
    two of the requester's own currently-reserved setups. Neither setup's
    reservation is affected -- only that one field's value moves between
    the two Setup rows once the request is approved.
    """

    __tablename__ = "swap_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False)
    requested_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False)

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
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SwapRequest id={0} status={1}>".format(self.id, self.status)

    @property
    def column_names(self):  # type: () -> list
        """The swapped column name(s) as a list, parsed from the stored comma-separated string."""
        if not self.column_name:
            return []
        return [part.strip() for part in self.column_name.split(",") if part.strip()]
