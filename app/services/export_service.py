"""Export service: orchestrates Excel export generation and logging."""
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from app.core.config import settings
from app.core.constants import AuditAction, ExportType
from app.models.excel_transaction_log import ExcelTransactionLog
from app.models.export_log import ExportLog
from app.models.user import User
from app.repositories.interfaces.i_export_repository import IExportRepository
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.schemas.reservation import ReservationFilter
from app.schemas.setup import SetupFilter
from app.services.audit_service import AuditService
from app.utils.excel_writer import build_export_context, write_excel_workbook

_SETUP_HEADERS = [
    "id", "product_id", "group_id", "ip_address", "hostname", "ssd", "hdd",
    "hardware_info", "capacity", "form_factor", "owner_id", "adapter",
    "aardvark", "quarch", "apc", "remote_server", "location", "remarks", "status",
]
_RESERVATION_HEADERS = [
    "id", "setup_id", "user_id", "reserved_from", "reserved_until", "status", "purpose",
]


class ExportService:
    """Generates Excel exports for Setups/Reservations and logs each export."""

    def __init__(
        self,
        export_repository: IExportRepository,
        setup_repository: ISetupRepository,
        reservation_repository: IReservationRepository,
        audit_service: AuditService,
    ) -> None:
        self._export_repository = export_repository
        self._setup_repository = setup_repository
        self._reservation_repository = reservation_repository
        self._audit_service = audit_service

    def _finalize(
        self, export_type: str, file_path: str, filters: Dict[str, Any], row_count: int, acting_user: User
    ) -> ExportLog:
        export_log = ExportLog(
            user_id=acting_user.id,
            export_type=export_type,
            file_path=file_path,
            filters=str(filters) if filters else None,
            row_count=row_count,
        )
        created = self._export_repository.create_export_log(export_log)
        batch_id = str(uuid.uuid4())
        self._export_repository.create_transaction_logs(
            [
                ExcelTransactionLog(
                    batch_id=batch_id,
                    operation="EXPORT",
                    entity_type=export_type,
                    row_number=row_count,
                    status="SUCCESS",
                    message="Export completed.",
                    user_id=acting_user.id,
                )
            ]
        )
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.EXPORT,
            entity_type=export_type,
            entity_id=created.id,
            new_value={"file_path": file_path, "row_count": row_count},
        )
        return created

    def export_setups(self, filters: SetupFilter, acting_user: User) -> ExportLog:
        setups = self._setup_repository.list_all(filters)
        rows: List[List[Any]] = [
            [
                setup.id, setup.product_id, setup.group_id, setup.ip_address, setup.hostname,
                setup.ssd, setup.hdd, setup.hardware_info, setup.capacity, setup.form_factor,
                setup.owner_id, setup.adapter, setup.aardvark, setup.quarch, setup.apc,
                setup.remote_server, setup.location, setup.remarks, setup.status,
            ]
            for setup in setups
        ]
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        file_name = "setups_{0}_{1}.xlsx".format(datetime.utcnow().strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:8])
        file_path = os.path.join(settings.EXPORT_DIR, file_name)
        context = build_export_context(acting_user.username, datetime.utcnow(), filters.dict(exclude_none=True), len(rows))
        write_excel_workbook(_SETUP_HEADERS, rows, "Setups", context, file_path)
        return self._finalize(ExportType.SETUPS, file_path, filters.dict(exclude_none=True), len(rows), acting_user)

    def export_reservations(self, filters: ReservationFilter, acting_user: User) -> ExportLog:
        reservations = self._reservation_repository.list_all(filters)
        rows: List[List[Any]] = [
            [r.id, r.setup_id, r.user_id, r.reserved_from, r.reserved_until, r.status, r.purpose]
            for r in reservations
        ]
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        file_name = "reservations_{0}_{1}.xlsx".format(
            datetime.utcnow().strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:8]
        )
        file_path = os.path.join(settings.EXPORT_DIR, file_name)
        context = build_export_context(acting_user.username, datetime.utcnow(), filters.dict(exclude_none=True), len(rows))
        write_excel_workbook(_RESERVATION_HEADERS, rows, "Reservations", context, file_path)
        return self._finalize(
            ExportType.RESERVATIONS, file_path, filters.dict(exclude_none=True), len(rows), acting_user
        )
