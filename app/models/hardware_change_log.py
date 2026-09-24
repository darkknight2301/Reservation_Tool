"""
HardwareChangeLog ORM model.

Append-only, per-field history of every CURRENT/EFFECTIVE hardware value
change made to a Setup by an approved Swap or Borrow transaction. Replaces
relying on free-text ``Reservation.remarks`` lines or a single
``previous_*_value`` snapshot (today's design -- see
ARCHITECTURE_ASSESSMENT.md section 3.2) as the only history: because this
table keeps one row per change instead of one slot that gets overwritten by
the next swap, a field changed more than once still has every intermediate
value queryable, and "current != baseline" (the UI highlighting rule) can
be answered directly from ``SetupHardwareBaseline`` + the latest row here
per field, without reconstructing history from prose.

Never updated or deleted by the app (mirrors ``AuditLog``'s append-only
discipline) -- it is itself part of the audit trail, scoped specifically to
hardware field values so the UI can query it without filtering the general
``AuditLog`` table's free-form JSON snapshots.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class HardwareChangeLog(Base):
    """One field-level hardware value change, resulting from an approved Swap or Borrow."""

    __tablename__ = "hardware_change_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # One of app.core.constants.HardwareChangeSource.ALL ("SWAP" | "BORROW").
    source = Column(String(20), nullable=False, index=True)
    # The SwapRequest.id or BorrowRequest.id that produced this change.
    # Not a hard FK (the two source tables are different), kept as a plain
    # indexed integer -- mirrors AuditLog.entity_id's same trade-off.
    source_request_id = Column(Integer, nullable=True, index=True)

    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    setup = relationship("Setup", foreign_keys=[setup_id])
    changed_by = relationship("User", foreign_keys=[changed_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<HardwareChangeLog setup_id={0} field={1} source={2}>".format(
            self.setup_id, self.field_name, self.source
        )
