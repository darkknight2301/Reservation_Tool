"""
ExcelTransactionLog ORM model.

Distinct from ``ExportLog`` (one summary row per export operation),
``ExcelTransactionLog`` records the outcome of *each individual row*
processed during an Excel import or export batch (e.g. row 5 of an import
failed validation, row 12 was upserted as an UPDATE). This gives a
per-record audit trail specifically for bulk Excel operations, independent
of the general-purpose ``AuditLog`` which records the resulting
CREATE/UPDATE against the target entity itself.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExcelTransactionLog(Base):
    """One row-level outcome record within an Excel import/export batch."""

    __tablename__ = "excel_transaction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), nullable=False, index=True)  # UUID grouping one file's rows
    operation = Column(String(10), nullable=False)  # 'IMPORT' | 'EXPORT'
    entity_type = Column(String(50), nullable=False)
    row_number = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # 'SUCCESS' | 'ERROR' | 'SKIPPED'
    message = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<ExcelTransactionLog batch={0} row={1} status={2}>".format(
            self.batch_id, self.row_number, self.status
        )
