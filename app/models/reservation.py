"""Reservation ORM model. Source of truth for a setup's reserved time window."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import ReservationStatus
from app.db.base import Base


class Reservation(Base):
    """A time-bound claim on a Setup by a User (the 'Reserved Time' record)."""

    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    reserved_from = Column(DateTime, nullable=False)
    reserved_until = Column(DateTime, nullable=False)

    status = Column(String(20), nullable=False, default=ReservationStatus.ACTIVE, index=True)
    purpose = Column(String(500), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    setup = relationship("Setup", back_populates="reservations")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Reservation id={0} setup_id={1} status={2}>".format(self.id, self.setup_id, self.status)
