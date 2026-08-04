"""Import service: validates and upserts Setup records from an Excel workbook."""
import uuid
from typing import Any, Dict, List

from pydantic import ValidationError

from app.core.constants import AuditAction
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
from app.services.audit_service import AuditService
from app.utils.excel_reader import read_setup_import_rows


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
    ) -> None:
        self._setup_repository = setup_repository
        self._product_repository = product_repository
        self._group_repository = group_repository
        self._user_repository = user_repository
        self._export_repository = export_repository
        self._audit_service = audit_service

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
