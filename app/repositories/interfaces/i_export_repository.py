"""Repository interface (Protocol) for ExportLog and ExcelTransactionLog entries."""
from typing import List, Protocol

from app.models.excel_transaction_log import ExcelTransactionLog
from app.models.export_log import ExportLog


class IExportRepository(Protocol):
    """Persistence contract for ExportLog and ExcelTransactionLog entries."""

    def create_export_log(self, export_log: ExportLog) -> ExportLog:
        ...

    def create_transaction_logs(self, logs: List[ExcelTransactionLog]) -> List[ExcelTransactionLog]:
        ...

    def list_transaction_logs_by_batch(self, batch_id: str) -> List[ExcelTransactionLog]:
        ...
