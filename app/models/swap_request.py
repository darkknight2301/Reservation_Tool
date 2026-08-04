"""SwapRequest ORM model."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import SwapStatus
from app.db.base import Base


class SwapRequest(Base):
    """A request to move an active reservation from one setup to another."""

    __tablename__ = "swap_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    current_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False)
    requested_setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False)

    status = Column(String(20), nullable=False, default=SwapStatus.PENDING, index=True)
    reason = Column(String(500), nullable=True)

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
