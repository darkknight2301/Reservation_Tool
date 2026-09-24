"""
SetupHardwareBaseline ORM model.

Holds the ORIGINAL/BASELINE value of every swappable hardware field for a
Setup, captured exactly once (at Setup creation, or backfilled from
existing data by the migration that introduces this table) and never
updated afterward by any service. ``setups.<field>`` continues to hold the
CURRENT/EFFECTIVE value, exactly as it does today (see ``app.models.setup``)
-- this table adds the missing other half required by the business rule
"Maintain two views of hardware information ... Do not destroy original
hardware information," without touching any existing, working column.

Mirrors ``app.services.swap_service.SWAPPABLE_SETUP_FIELDS`` (the only
fixed columns any Swap/Borrow transaction is ever allowed to change) plus
each column already being nullable on ``Setup`` -- a field a Setup never
had (e.g. no ``apc``) simply has a ``None`` baseline too.

One row per Setup (enforced by the unique constraint on ``setup_id``); a
Setup created before this table existed is backfilled with its
then-current values as its baseline by the introducing migration.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SetupHardwareBaseline(Base):
    """The immutable, original hardware configuration of one Setup."""

    __tablename__ = "setup_hardware_baseline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, unique=True, index=True)

    ssd = Column(String(100), nullable=True)
    hdd = Column(String(100), nullable=True)
    hardware_info = Column(String(500), nullable=True)
    capacity = Column(String(100), nullable=True)
    form_factor = Column(String(50), nullable=True)
    adapter = Column(String(100), nullable=True)
    aardvark = Column(String(100), nullable=True)
    quarch = Column(String(100), nullable=True)
    apc = Column(String(100), nullable=True)
    remote_server = Column(String(255), nullable=True)

    captured_at = Column(DateTime, nullable=False, server_default=func.now())

    setup = relationship("Setup", foreign_keys=[setup_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SetupHardwareBaseline setup_id={0}>".format(self.setup_id)
