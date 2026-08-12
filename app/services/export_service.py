"""Export service: orchestrates Excel export generation and logging."""
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.constants import AuditAction, ExportType
from app.core.exceptions import ValidationAppError
from app.models.excel_transaction_log import ExcelTransactionLog
from app.models.export_log import ExportLog
from app.models.user import User
from app.repositories.interfaces.i_export_repository import IExportRepository
from app.repositories.interfaces.i_reservation_repository import IReservationRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.schemas.reservation import ReservationFilter
from app.schemas.setup import SetupFilter
from app.services.audit_service import AuditService
from app.services.template_service import TemplateService
from app.utils.excel_log_rotator import append_excel_transactions
from app.utils.excel_reader import SETUP_IMPORT_COLUMNS
from app.utils.excel_writer import build_export_context, write_excel_workbook

_SETUP_HEADERS = [
    "id", "product_id", "group_id", "ip_address", "hostname", "ssd", "hdd",
    "hardware_info", "capacity", "form_factor", "owner_id", "adapter",
    "aardvark", "quarch", "apc", "remote_server", "location", "remarks", "status",
]
_RESERVATION_HEADERS = [
    "id", "setup_id", "user_id", "reserved_from", "reserved_until", "status", "remarks",
]


class ExportService:
    """Generates Excel exports for Setups/Reservations and logs each export."""

    def __init__(
        self,
        export_repository: IExportRepository,
        setup_repository: ISetupRepository,
        reservation_repository: IReservationRepository,
        audit_service: AuditService,
        template_service: Optional[TemplateService] = None,
    ) -> None:
        self._export_repository = export_repository
        self._setup_repository = setup_repository
        self._reservation_repository = reservation_repository
        self._audit_service = audit_service
        self._template_service = template_service

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
        message = "Export completed." if row_count > 0 else "Export completed (empty template generated)."
        self._export_repository.create_transaction_logs(
            [
                ExcelTransactionLog(
                    batch_id=batch_id,
                    operation="EXPORT",
                    entity_type=export_type,
                    row_number=row_count,
                    status="SUCCESS",
                    message=message,
                    user_id=acting_user.id,
                )
            ]
        )
        append_excel_transactions(
            [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "operation": "EXPORT",
                    "entity_type": export_type,
                    "row_number": row_count,
                    "status": "SUCCESS",
                    "message": message,
                    "user": acting_user.username,
                }
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
        """
        Export Setups matching the given filters. If no rows match (e.g. a
        brand-new Product with no Setups configured yet), an empty
        *import-ready template* is generated instead of a blank export, so
        the user can immediately fill it in and re-upload via Import.
        """
        setups = self._setup_repository.list_all(filters)
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        file_name = "setups_{0}_{1}.xlsx".format(datetime.utcnow().strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:8])
        file_path = os.path.join(settings.EXPORT_DIR, file_name)
        context = build_export_context(acting_user.username, datetime.utcnow(), filters.dict(exclude_none=True), len(setups))

        if setups:
            rows: List[List[Any]] = [
                [
                    setup.id, setup.product_id, setup.group_id, setup.ip_address, setup.hostname,
                    setup.ssd, setup.hdd, setup.hardware_info, setup.capacity, setup.form_factor,
                    setup.owner_id, setup.adapter, setup.aardvark, setup.quarch, setup.apc,
                    setup.remote_server, setup.location, setup.remarks, setup.status,
                ]
                for setup in setups
            ]
            context["Note"] = "Full export."
            write_excel_workbook(_SETUP_HEADERS, rows, "Setups", context, file_path)
        else:
            context["Note"] = "No Setups found for the given filters -- empty import template generated instead."
            write_excel_workbook(SETUP_IMPORT_COLUMNS, [], "Template", context, file_path)

        return self._finalize(ExportType.SETUPS, file_path, filters.dict(exclude_none=True), len(setups), acting_user)

    def export_reservations(self, filters: ReservationFilter, acting_user: User) -> ExportLog:
        reservations = self._reservation_repository.list_all(filters)
        rows: List[List[Any]] = [
            [r.id, r.setup_id, r.user_id, r.reserved_from, r.reserved_until, r.status, r.remarks]
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

    def export_setups_for_product(self, product_id: int, acting_user: User) -> ExportLog:
        """
        Export every Setup for a single Product using that Product's CURRENT
        dynamic template: mandatory columns followed by the product's custom
        columns, in template order, with each row's custom field values
        merged in. Falls back to an empty, import-ready template (using the
        same dynamic header set) when the product has no setups yet.
        """
        if self._template_service is None:
            raise ValidationAppError("Template-aware export is not configured.")

        filters = SetupFilter(product_id=product_id)
        setups = self._setup_repository.list_all(filters)
        custom_columns = self._template_service.get_custom_columns(product_id)
        custom_names = [col.name for col in custom_columns]
        headers = list(_SETUP_HEADERS) + custom_names

        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        file_name = "setups_product{0}_{1}_{2}.xlsx".format(
            product_id, datetime.utcnow().strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:8]
        )
        file_path = os.path.join(settings.EXPORT_DIR, file_name)
        context = build_export_context(acting_user.username, datetime.utcnow(), {"product_id": product_id}, len(setups))

        if setups:
            values_by_setup = self._template_service.get_values_map_for_setups(
                [s.id for s in setups], product_id
            )
            rows: List[List[Any]] = []
            for setup in setups:
                base_row = [
                    setup.id, setup.product_id, setup.group_id, setup.ip_address, setup.hostname,
                    setup.ssd, setup.hdd, setup.hardware_info, setup.capacity, setup.form_factor,
                    setup.owner_id, setup.adapter, setup.aardvark, setup.quarch, setup.apc,
                    setup.remote_server, setup.location, setup.remarks, setup.status,
                ]
                custom_values = values_by_setup.get(setup.id, {})
                base_row.extend(custom_values.get(name) for name in custom_names)
                rows.append(base_row)
            context["Note"] = "Full export using the current product template."
            write_excel_workbook(headers, rows, "Setups", context, file_path)
        else:
            context["Note"] = "No Setups found for this Product -- empty import template generated instead."
            write_excel_workbook(SETUP_IMPORT_COLUMNS + custom_names, [], "Template", context, file_path)

        return self._finalize(ExportType.SETUPS, file_path, {"product_id": product_id}, len(setups), acting_user)

    def generate_setup_template(self, acting_user: User) -> ExportLog:
        """Explicitly generate an empty, import-ready Setup template (e.g. for a brand-new Product)."""
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)
        file_name = "setups_template_{0}_{1}.xlsx".format(datetime.utcnow().strftime("%Y%m%dT%H%M%S"), uuid.uuid4().hex[:8])
        file_path = os.path.join(settings.EXPORT_DIR, file_name)
        context = build_export_context(acting_user.username, datetime.utcnow(), {}, 0)
        context["Note"] = "Empty import template."
        write_excel_workbook(SETUP_IMPORT_COLUMNS, [], "Template", context, file_path)
        return self._finalize(ExportType.SETUPS, file_path, {}, 0, acting_user)
