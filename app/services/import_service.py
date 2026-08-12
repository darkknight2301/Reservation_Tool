"""Import service: validates and upserts Setup records from an Excel workbook."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.excel_transaction_log import ExcelTransactionLog
from app.models.setup import Setup
from app.models.user import User
from app.repositories.interfaces.i_export_repository import IExportRepository
from app.repositories.interfaces.i_group_repository import IGroupRepository
from app.repositories.interfaces.i_product_repository import IProductRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_user_repository import IUserRepository
from app.schemas.export_import import ImportResultResponse, ImportRowError
from app.schemas.setup import SetupCreateRequest
from app.schemas.template import DetectedColumnsResponse
from app.services.audit_service import AuditService
from app.services.template_service import TemplateService
from app.utils.excel_log_rotator import append_excel_transactions
from app.utils.excel_reader import SETUP_IMPORT_COLUMNS, read_setup_import_rows, read_workbook_headers_and_rows


class ImportService:
    """Validates and upserts Setup rows parsed from an uploaded Excel workbook."""

    def __init__(
        self,
        setup_repository: ISetupRepository,
        product_repository: IProductRepository,
        group_repository: IGroupRepository,
        user_repository: IUserRepository,
        export_repository: IExportRepository,
        audit_service: AuditService,
        template_service: Optional[TemplateService] = None,
    ) -> None:
        self._setup_repository = setup_repository
        self._product_repository = product_repository
        self._group_repository = group_repository
        self._user_repository = user_repository
        self._export_repository = export_repository
        self._audit_service = audit_service
        self._template_service = template_service

    def import_setups(self, file_path: str, acting_user: User) -> ImportResultResponse:
        """
        Parse, validate, and (on full validity) commit every row of a Setup
        import workbook in a single all-or-nothing batch.
        """
        rows = read_setup_import_rows(file_path)
        batch_id = str(uuid.uuid4())
        errors: List[ImportRowError] = []
        transaction_logs: List[ExcelTransactionLog] = []
        resolved_rows: List[Dict[str, Any]] = []

        for row_number, raw_row in enumerate(rows, start=2):  # header is row 1
            row_errors = self._validate_row(raw_row, row_number)
            if row_errors:
                errors.extend(row_errors)
                transaction_logs.append(
                    ExcelTransactionLog(
                        batch_id=batch_id, operation="IMPORT", entity_type="Setup", row_number=row_number,
                        status="ERROR", message="; ".join(e.message for e in row_errors), user_id=acting_user.id,
                    )
                )
            else:
                resolved_rows.append(raw_row)

        if errors:
            self._export_repository.create_transaction_logs(transaction_logs)
            append_excel_transactions(
                [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "operation": log.operation,
                        "entity_type": log.entity_type,
                        "row_number": log.row_number,
                        "status": log.status,
                        "message": log.message,
                        "user": acting_user.username,
                    }
                    for log in transaction_logs
                ]
            )
            return ImportResultResponse(
                batch_id=batch_id, entity_type="Setup", total_rows=len(rows), created_count=0,
                updated_count=0, error_count=len(errors), errors=errors, committed=False,
            )

        created_count = 0
        updated_count = 0
        for row_number, raw_row in enumerate(resolved_rows, start=2):
            product = self._product_repository.get_by_name(raw_row["product_name"])
            group = self._group_repository.get_by_name(raw_row["group_name"]) if raw_row.get("group_name") else None
            owner = (
                self._user_repository.get_by_username(raw_row["owner_username"])
                if raw_row.get("owner_username")
                else None
            )

            payload = SetupCreateRequest(
                product_id=product.id,
                group_id=group.id if group else None,
                ip_address=raw_row["ip_address"],
                hostname=raw_row["hostname"],
                ssd=raw_row.get("ssd"),
                hdd=raw_row.get("hdd"),
                hardware_info=raw_row.get("hardware_info"),
                capacity=raw_row.get("capacity"),
                form_factor=raw_row.get("form_factor"),
                owner_id=owner.id if owner else None,
                adapter=raw_row.get("adapter"),
                aardvark=raw_row.get("aardvark"),
                quarch=raw_row.get("quarch"),
                apc=raw_row.get("apc"),
                remote_server=raw_row.get("remote_server"),
                location=raw_row["location"],
                remarks=raw_row.get("remarks"),
            )

            existing = self._setup_repository.get_by_ip_or_hostname(payload.ip_address, payload.hostname)
            if existing is not None:
                for field_name, field_value in payload.dict().items():
                    setattr(existing, field_name, field_value)
                self._setup_repository.update(existing)
                updated_count += 1
                status = "SUCCESS"
                message = "Updated existing setup."
                entity_id = existing.id
            else:
                created = self._setup_repository.create(Setup(**payload.dict()))
                created_count += 1
                status = "SUCCESS"
                message = "Created new setup."
                entity_id = created.id

            transaction_logs.append(
                ExcelTransactionLog(
                    batch_id=batch_id, operation="IMPORT", entity_type="Setup", row_number=row_number,
                    status=status, message=message, user_id=acting_user.id,
                )
            )
            self._audit_service.record(
                user_id=acting_user.id, action=AuditAction.IMPORT, entity_type="Setup", entity_id=entity_id,
                new_value={"hostname": payload.hostname, "ip_address": payload.ip_address},
            )

        self._export_repository.create_transaction_logs(transaction_logs)
        append_excel_transactions(
            [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "operation": log.operation,
                    "entity_type": log.entity_type,
                    "row_number": log.row_number,
                    "status": log.status,
                    "message": log.message,
                    "user": acting_user.username,
                }
                for log in transaction_logs
            ]
        )

        return ImportResultResponse(
            batch_id=batch_id, entity_type="Setup", total_rows=len(rows), created_count=created_count,
            updated_count=updated_count, error_count=0, errors=[], committed=True,
        )

    def _validate_row(self, raw_row: Dict[str, Any], row_number: int) -> List[ImportRowError]:
        """Validate a single raw import row, resolving name-based FKs and running schema validation."""
        errors: List[ImportRowError] = []

        product = self._product_repository.get_by_name(raw_row.get("product_name") or "")
        if product is None:
            errors.append(
                ImportRowError(row=row_number, field="product_name", message="Unknown product: {0}".format(raw_row.get("product_name")))
            )

        if raw_row.get("group_name"):
            if self._group_repository.get_by_name(raw_row["group_name"]) is None:
                errors.append(
                    ImportRowError(row=row_number, field="group_name", message="Unknown group: {0}".format(raw_row["group_name"]))
                )

        if raw_row.get("owner_username"):
            if self._user_repository.get_by_username(raw_row["owner_username"]) is None:
                errors.append(
                    ImportRowError(
                        row=row_number, field="owner_username", message="Unknown user: {0}".format(raw_row["owner_username"])
                    )
                )

        try:
            SetupCreateRequest(
                product_id=product.id if product else 0,
                group_id=None,
                ip_address=raw_row.get("ip_address") or "",
                hostname=raw_row.get("hostname") or "",
                ssd=raw_row.get("ssd"),
                hdd=raw_row.get("hdd"),
                hardware_info=raw_row.get("hardware_info"),
                capacity=raw_row.get("capacity"),
                form_factor=raw_row.get("form_factor"),
                owner_id=None,
                adapter=raw_row.get("adapter"),
                aardvark=raw_row.get("aardvark"),
                quarch=raw_row.get("quarch"),
                apc=raw_row.get("apc"),
                remote_server=raw_row.get("remote_server"),
                location=raw_row.get("location") or "",
                remarks=raw_row.get("remarks"),
            )
        except ValidationError as exc:
            for error in exc.errors():
                field_name = str(error["loc"][0]) if error.get("loc") else None
                errors.append(ImportRowError(row=row_number, field=field_name, message=error["msg"]))

        return errors

    # --- Product-template-aware import (dynamic columns) ------------------------

    _CORE_REQUIRED_HEADERS = ("ip_address", "hostname", "location")

    def detect_new_columns(self, file_path: str, product_id: int) -> DetectedColumnsResponse:
        """
        Compare an uploaded workbook's headers against a Product's current
        template and report which headers are already known vs. brand new,
        without importing anything.
        """
        if self._template_service is None:
            raise ValidationAppError("Template-aware import is not configured.")
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product with id {0} was not found.".format(product_id))

        headers, rows = read_workbook_headers_and_rows(file_path)
        known_custom_names = {col.name for col in self._template_service.get_custom_columns(product_id)}
        known = set(SETUP_IMPORT_COLUMNS) | known_custom_names | {"product_name"}
        new_columns = [h for h in headers if h not in known]
        known_columns = [h for h in headers if h in known]
        return DetectedColumnsResponse(
            product_id=product_id, known_columns=known_columns, new_columns=new_columns, total_rows=len(rows)
        )

    def import_setups_for_product(
        self, file_path: str, product_id: int, acting_user: User, accept_new_columns: bool = False
    ) -> ImportResultResponse:
        """
        Import Setups for a single, pre-selected Product, validating every
        column (mandatory + the product's current custom columns) against
        that Product's template.

        If the workbook contains columns not yet in the template:
          * ``accept_new_columns=False`` (default): nothing is imported; the
            result reports ``new_columns`` so the caller can prompt the user
            to accept or reject them ("New columns detected").
          * ``accept_new_columns=True``: the new columns are added to the
            product's template first (as String columns), then the import
            proceeds using the now-expanded template.
        """
        if self._template_service is None:
            raise ValidationAppError("Template-aware import is not configured.")
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product with id {0} was not found.".format(product_id))

        headers, rows = read_workbook_headers_and_rows(file_path)
        missing_core = [h for h in self._CORE_REQUIRED_HEADERS if h not in headers]
        if missing_core:
            raise ValidationAppError(
                "The uploaded workbook is missing required column(s): {0}".format(", ".join(missing_core))
            )

        known_custom_names = {col.name for col in self._template_service.get_custom_columns(product_id)}
        known = set(SETUP_IMPORT_COLUMNS) | known_custom_names | {"product_name"}
        new_columns = [h for h in headers if h not in known]

        batch_id = str(uuid.uuid4())
        if new_columns and not accept_new_columns:
            return ImportResultResponse(
                batch_id=batch_id, entity_type="Setup", total_rows=len(rows), created_count=0, updated_count=0,
                error_count=0, errors=[], committed=False, new_columns=new_columns,
            )

        if new_columns and accept_new_columns:
            self._template_service.add_columns_from_names(product_id, new_columns, acting_user)
            known_custom_names = known_custom_names | set(new_columns)

        errors: List[ImportRowError] = []
        transaction_logs: List[ExcelTransactionLog] = []
        row_custom_values: List[Dict[str, Any]] = []

        for row_number, raw_row in enumerate(rows, start=2):  # header is row 1
            row_errors: List[ImportRowError] = []
            group = self._group_repository.get_by_name(raw_row["group_name"]) if raw_row.get("group_name") else None
            if raw_row.get("group_name") and group is None:
                row_errors.append(ImportRowError(row=row_number, field="group_name", message="Unknown group: {0}".format(raw_row["group_name"])))
            owner = (
                self._user_repository.get_by_username(raw_row["owner_username"]) if raw_row.get("owner_username") else None
            )
            if raw_row.get("owner_username") and owner is None:
                row_errors.append(ImportRowError(row=row_number, field="owner_username", message="Unknown user: {0}".format(raw_row["owner_username"])))

            try:
                SetupCreateRequest(
                    product_id=product_id,
                    group_id=group.id if group else None,
                    ip_address=raw_row.get("ip_address") or "",
                    hostname=raw_row.get("hostname") or "",
                    ssd=raw_row.get("ssd"), hdd=raw_row.get("hdd"), hardware_info=raw_row.get("hardware_info"),
                    capacity=raw_row.get("capacity"), form_factor=raw_row.get("form_factor"),
                    owner_id=owner.id if owner else None, adapter=raw_row.get("adapter"),
                    aardvark=raw_row.get("aardvark"), quarch=raw_row.get("quarch"), apc=raw_row.get("apc"),
                    remote_server=raw_row.get("remote_server"), location=raw_row.get("location") or "",
                    remarks=raw_row.get("remarks"),
                )
            except ValidationError as exc:
                for error in exc.errors():
                    field_name = str(error["loc"][0]) if error.get("loc") else None
                    row_errors.append(ImportRowError(row=row_number, field=field_name, message=error["msg"]))

            custom_raw = {name: raw_row[name] for name in known_custom_names if raw_row.get(name) not in (None, "")}
            try:
                self._template_service.validate_and_serialize_values(product_id, custom_raw)
            except ValidationAppError as exc:
                for field_error in exc.details.get("errors", []):
                    row_errors.append(ImportRowError(row=row_number, field=field_error.get("field"), message=field_error.get("message")))

            if row_errors:
                errors.extend(row_errors)
                transaction_logs.append(
                    ExcelTransactionLog(
                        batch_id=batch_id, operation="IMPORT", entity_type="Setup", row_number=row_number,
                        status="ERROR", message="; ".join(e.message for e in row_errors), user_id=acting_user.id,
                    )
                )
            else:
                row_custom_values.append({"row": raw_row, "custom": custom_raw})

        if errors:
            self._export_repository.create_transaction_logs(transaction_logs)
            return ImportResultResponse(
                batch_id=batch_id, entity_type="Setup", total_rows=len(rows), created_count=0, updated_count=0,
                error_count=len(errors), errors=errors, committed=False, new_columns=new_columns,
            )

        created_count = 0
        updated_count = 0
        for row_number, entry in enumerate(row_custom_values, start=2):
            raw_row = entry["row"]
            group = self._group_repository.get_by_name(raw_row["group_name"]) if raw_row.get("group_name") else None
            owner = self._user_repository.get_by_username(raw_row["owner_username"]) if raw_row.get("owner_username") else None
            payload = SetupCreateRequest(
                product_id=product_id, group_id=group.id if group else None,
                ip_address=raw_row["ip_address"], hostname=raw_row["hostname"],
                ssd=raw_row.get("ssd"), hdd=raw_row.get("hdd"), hardware_info=raw_row.get("hardware_info"),
                capacity=raw_row.get("capacity"), form_factor=raw_row.get("form_factor"),
                owner_id=owner.id if owner else None, adapter=raw_row.get("adapter"),
                aardvark=raw_row.get("aardvark"), quarch=raw_row.get("quarch"), apc=raw_row.get("apc"),
                remote_server=raw_row.get("remote_server"), location=raw_row["location"], remarks=raw_row.get("remarks"),
            )

            existing = self._setup_repository.get_by_ip_or_hostname(payload.ip_address, payload.hostname)
            if existing is not None:
                for field_name, field_value in payload.dict().items():
                    setattr(existing, field_name, field_value)
                setup = self._setup_repository.update(existing)
                updated_count += 1
                status, message = "SUCCESS", "Updated existing setup."
            else:
                setup = self._setup_repository.create(Setup(**payload.dict()))
                created_count += 1
                status, message = "SUCCESS", "Created new setup."

            if entry["custom"]:
                self._template_service.set_setup_values(setup.id, product_id, entry["custom"], acting_user)

            transaction_logs.append(
                ExcelTransactionLog(
                    batch_id=batch_id, operation="IMPORT", entity_type="Setup", row_number=row_number,
                    status=status, message=message, user_id=acting_user.id,
                )
            )
            self._audit_service.record(
                user_id=acting_user.id, action=AuditAction.IMPORT, entity_type="Setup", entity_id=setup.id,
                new_value={"hostname": payload.hostname, "ip_address": payload.ip_address},
            )

        self._export_repository.create_transaction_logs(transaction_logs)
        append_excel_transactions(
            [
                {
                    "timestamp": datetime.utcnow().isoformat(), "operation": log.operation, "entity_type": log.entity_type,
                    "row_number": log.row_number, "status": log.status, "message": log.message, "user": acting_user.username,
                }
                for log in transaction_logs
            ]
        )

        return ImportResultResponse(
            batch_id=batch_id, entity_type="Setup", total_rows=len(rows), created_count=created_count,
            updated_count=updated_count, error_count=0, errors=[], committed=True, new_columns=[],
        )
