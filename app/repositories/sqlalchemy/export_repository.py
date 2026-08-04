"""SQLAlchemy implementation of the Export/ExcelTransactionLog repository."""
from typing import List

from sqlalchemy.orm import Session

from app.models.excel_transaction_log import ExcelTransactionLog
from app.models.export_log import ExportLog


class ExportRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IExportRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_export_log(self, export_log: ExportLog) -> ExportLog:
        self._db.add(export_log)
        self._db.flush()
        self._db.refresh(export_log)
        return export_log

    def create_transaction_logs(self, logs: List[ExcelTransactionLog]) -> List[ExcelTransactionLog]:
        self._db.add_all(logs)
        self._db.flush()
        for log in logs:
            self._db.refresh(log)
        return logs

    def list_transaction_logs_by_batch(self, batch_id: str) -> List[ExcelTransactionLog]:
        return (
            self._db.query(ExcelTransactionLog)
            .filter(ExcelTransactionLog.batch_id == batch_id)
            .order_by(ExcelTransactionLog.row_number.asc())
            .all()
        )
