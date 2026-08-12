"""
Setup ORM model.

Represents a reservable Linux CLI hardware setup, carrying every piece of
hardware/network metadata required by the business (IP, hostname, storage,
lab equipment references, location, etc.). ``status`` is a cached/derived
column kept in sync by the service layer inside the same transaction as any
reservation state change, so automation can filter on it directly without a
join against ``reservations``.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import SetupStatus
from app.db.base import Base


class Setup(Base):
    """A reservable Linux CLI setup and its hardware/network metadata."""

    __tablename__ = "setups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    hostname = Column(String(255), nullable=False, unique=True, index=True)
    ssd = Column(String(100), nullable=True)
    hdd = Column(String(100), nullable=True)
    hardware_info = Column(String(500), nullable=True)
    capacity = Column(String(100), nullable=True)
    form_factor = Column(String(50), nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    adapter = Column(String(100), nullable=True)
    aardvark = Column(String(100), nullable=True)
    quarch = Column(String(100), nullable=True)
    apc = Column(String(100), nullable=True)
    remote_server = Column(String(255), nullable=True)
    location = Column(String(255), nullable=False)
    remarks = Column(String(1000), nullable=True)

    status = Column(String(20), nullable=False, default=SetupStatus.AVAILABLE, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="setups")
    group = relationship("Group", back_populates="setups")
    owner = relationship("User", foreign_keys=[owner_id])
    reservations = relationship("Reservation", back_populates="setup")
    custom_field_values = relationship(
        "SetupCustomFieldValue", back_populates="setup", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Setup id={0} hostname={1} status={2}>".format(self.id, self.hostname, self.status)
