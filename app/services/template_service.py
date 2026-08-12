"""
Template service: business logic for a Product's dynamic table/template
(custom columns) and for validating + storing per-Setup custom field values.

This is additive to the existing Setup/Product feature set: it never
touches the fixed, mandatory Setup columns (ip_address, owner, location,
remarks, group, product, reservation) and never requires a schema
migration to add a new custom column -- a new column is just a new
``ProductTemplateColumn`` row.
"""
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.constants import AuditAction, ColumnDataType, MANDATORY_TEMPLATE_COLUMNS
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.product_template_column import ProductTemplateColumn
from app.models.user import User
from app.repositories.interfaces.i_product_repository import IProductRepository
from app.repositories.interfaces.i_template_repository import ITemplateRepository
from app.schemas.template import (
    MandatoryColumnResponse,
    ProductTemplateResponse,
    TemplateColumnCreateRequest,
    TemplateColumnResponse,
    TemplateColumnUpdateRequest,
)
from app.services.audit_service import AuditService


class TemplateService:
    """Business logic for Product template (custom column) management."""

    def __init__(
        self,
        template_repository: ITemplateRepository,
        product_repository: IProductRepository,
        audit_service: AuditService,
    ) -> None:
        self._template_repository = template_repository
        self._product_repository = product_repository
        self._audit_service = audit_service

    # --- Template read -----------------------------------------------------

    def _require_product(self, product_id: int):
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product with id {0} was not found.".format(product_id))
        return product

    def get_custom_columns(self, product_id: int) -> List[ProductTemplateColumn]:
        """Raw ORM custom columns for a product, in display order. Used internally by import/export."""
        return self._template_repository.list_columns_for_product(product_id)

    def get_template(self, product_id: int) -> ProductTemplateResponse:
        self._require_product(product_id)
        custom_columns = self._template_repository.list_columns_for_product(product_id)
        return ProductTemplateResponse(
            product_id=product_id,
            mandatory_columns=[MandatoryColumnResponse(**col) for col in MANDATORY_TEMPLATE_COLUMNS],
            custom_columns=[TemplateColumnResponse.from_orm_column(col) for col in custom_columns],
        )

    # --- Template mutation ---------------------------------------------------

    def add_column(self, product_id: int, payload: TemplateColumnCreateRequest, acting_user: User) -> TemplateColumnResponse:
        self._require_product(product_id)
        normalized_name = payload.name.strip().lower().replace(" ", "_")
        self._reject_mandatory_name(normalized_name)

        if self._template_repository.get_column_by_name(product_id, normalized_name) is not None:
            raise ConflictError("A column named '{0}' already exists on this product's template.".format(normalized_name))

        existing_columns = self._template_repository.list_columns_for_product(product_id)
        next_order = max([col.order_index for col in existing_columns], default=-1) + 1

        column = ProductTemplateColumn(
            product_id=product_id,
            name=normalized_name,
            label=(payload.label or payload.name).strip(),
            data_type=payload.data_type,
            required=payload.required,
            default_value=payload.default_value,
            allowed_values=json.dumps(payload.allowed_values) if payload.allowed_values else None,
            order_index=next_order,
        )
        created = self._template_repository.create_column(column)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="ProductTemplateColumn",
            entity_id=created.id,
            new_value={"product_id": product_id, "name": created.name, "data_type": created.data_type},
        )
        return TemplateColumnResponse.from_orm_column(created)

    def update_column(
        self, product_id: int, column_id: int, payload: TemplateColumnUpdateRequest, acting_user: User
    ) -> TemplateColumnResponse:
        column = self._get_owned_column(product_id, column_id)
        old_value = {"label": column.label, "required": column.required, "default_value": column.default_value}

        if payload.label is not None:
            column.label = payload.label.strip() or column.label
        if payload.required is not None:
            column.required = payload.required
        if payload.default_value is not None:
            column.default_value = payload.default_value
        if payload.allowed_values is not None:
            if column.data_type != ColumnDataType.DROPDOWN:
                raise ValidationAppError("allowed_values can only be set on a Dropdown column.")
            column.allowed_values = json.dumps(payload.allowed_values)

        updated = self._template_repository.update_column(column)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="ProductTemplateColumn",
            entity_id=updated.id,
            old_value=old_value,
            new_value={"label": updated.label, "required": updated.required, "default_value": updated.default_value},
        )
        return TemplateColumnResponse.from_orm_column(updated)

    def delete_column(self, product_id: int, column_id: int, acting_user: User) -> None:
        column = self._get_owned_column(product_id, column_id)
        self._template_repository.delete_column(column_id)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="ProductTemplateColumn",
            entity_id=column_id,
            old_value={"product_id": product_id, "name": column.name},
        )

    def reorder_columns(self, product_id: int, column_ids: List[int], acting_user: User) -> List[TemplateColumnResponse]:
        self._require_product(product_id)
        existing_columns = {col.id: col for col in self._template_repository.list_columns_for_product(product_id)}
        unknown = [cid for cid in column_ids if cid not in existing_columns]
        if unknown:
            raise ValidationAppError("Unknown column id(s) for this product: {0}".format(unknown))
        if set(column_ids) != set(existing_columns.keys()):
            raise ValidationAppError("Reorder must include every custom column exactly once.")

        for index, column_id in enumerate(column_ids):
            column = existing_columns[column_id]
            column.order_index = index
            self._template_repository.update_column(column)

        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="ProductTemplateColumn",
            entity_id=product_id,
            new_value={"reordered": column_ids},
        )
        return [
            TemplateColumnResponse.from_orm_column(existing_columns[cid]) for cid in column_ids
        ]

    def _get_owned_column(self, product_id: int, column_id: int) -> ProductTemplateColumn:
        column = self._template_repository.get_column_by_id(column_id)
        if column is None or column.product_id != product_id:
            raise NotFoundError("Custom column {0} was not found on product {1}.".format(column_id, product_id))
        return column

    @staticmethod
    def _reject_mandatory_name(name: str) -> None:
        mandatory_names = {col["name"] for col in MANDATORY_TEMPLATE_COLUMNS}
        if name in mandatory_names:
            raise ConflictError("'{0}' is a mandatory column and cannot be added, renamed, or removed.".format(name))

    # --- Value validation / (de)serialization --------------------------------

    def validate_and_serialize_values(self, product_id: int, raw_values: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Validate a dict of {column_name: raw_value} against the product's custom
        columns and return {column_name: serialized_string_value}, applying each
        column's default_value when a required column is missing. Raises
        ValidationAppError (with per-field details) on any type/required/dropdown
        violation.
        """
        columns = self._template_repository.list_columns_for_product(product_id)
        columns_by_name = {col.name: col for col in columns}
        errors: List[Dict[str, str]] = []
        serialized: Dict[str, Optional[str]] = {}

        for column in columns:
            has_value = column.name in raw_values and raw_values[column.name] not in (None, "")
            if not has_value:
                if column.required and column.default_value is None:
                    errors.append({"field": column.name, "message": "'{0}' is required.".format(column.label)})
                    continue
                if column.default_value is not None:
                    serialized[column.name] = column.default_value
                continue
            try:
                serialized[column.name] = self._serialize_value(column, raw_values[column.name])
            except ValueError as exc:
                errors.append({"field": column.name, "message": str(exc)})

        unknown_fields = [name for name in raw_values.keys() if name not in columns_by_name]
        for field_name in unknown_fields:
            errors.append({"field": field_name, "message": "'{0}' is not defined in this product's template.".format(field_name)})

        if errors:
            raise ValidationAppError("One or more custom field values are invalid.", details={"errors": errors})

        return serialized

    @staticmethod
    def _serialize_value(column: ProductTemplateColumn, value: Any) -> str:
        data_type = column.data_type
        if data_type == ColumnDataType.STRING:
            return str(value)
        if data_type == ColumnDataType.INTEGER:
            return str(int(value))
        if data_type == ColumnDataType.FLOAT:
            return str(float(value))
        if data_type == ColumnDataType.BOOLEAN:
            if isinstance(value, bool):
                return str(value)
            text = str(value).strip().lower()
            if text in ("true", "1", "yes", "y"):
                return "True"
            if text in ("false", "0", "no", "n"):
                return "False"
            raise ValueError("'{0}' is not a valid boolean for column '{1}'.".format(value, column.label))
        if data_type == ColumnDataType.DATE:
            if isinstance(value, date):
                return value.isoformat()
            try:
                return datetime.fromisoformat(str(value)).date().isoformat()
            except ValueError:
                raise ValueError("'{0}' is not a valid date for column '{1}'.".format(value, column.label))
        if data_type == ColumnDataType.DATETIME:
            if isinstance(value, datetime):
                return value.isoformat()
            try:
                return datetime.fromisoformat(str(value)).isoformat()
            except ValueError:
                raise ValueError("'{0}' is not a valid datetime for column '{1}'.".format(value, column.label))
        if data_type == ColumnDataType.DROPDOWN:
            allowed = json.loads(column.allowed_values) if column.allowed_values else []
            if str(value) not in allowed:
                raise ValueError(
                    "'{0}' is not an allowed value for column '{1}' (allowed: {2}).".format(value, column.label, ", ".join(allowed))
                )
            return str(value)
        raise ValueError("Unsupported column data type: {0}".format(data_type))

    def get_values_map_for_setup(self, setup_id: int, product_id: int) -> Dict[str, Any]:
        columns_by_id = {col.id: col for col in self._template_repository.list_columns_for_product(product_id)}
        values = self._template_repository.get_values_for_setup(setup_id)
        return {
            columns_by_id[v.template_column_id].name: v.value
            for v in values
            if v.template_column_id in columns_by_id
        }

    def get_values_map_for_setups(self, setup_ids: List[int], product_id: int) -> Dict[int, Dict[str, Any]]:
        columns_by_id = {col.id: col for col in self._template_repository.list_columns_for_product(product_id)}
        grouped = self._template_repository.get_values_for_setups(setup_ids)
        result: Dict[int, Dict[str, Any]] = {}
        for setup_id, values in grouped.items():
            result[setup_id] = {
                columns_by_id[v.template_column_id].name: v.value
                for v in values
                if v.template_column_id in columns_by_id
            }
        return result

    def set_setup_values(self, setup_id: int, product_id: int, raw_values: Dict[str, Any], acting_user: User) -> Dict[str, Any]:
        serialized = self.validate_and_serialize_values(product_id, raw_values)
        columns_by_name = {col.name: col for col in self._template_repository.list_columns_for_product(product_id)}
        for name, value in serialized.items():
            self._template_repository.upsert_value(setup_id, columns_by_name[name].id, value)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="SetupCustomFieldValue",
            entity_id=setup_id,
            new_value=serialized,
        )
        return self.get_values_map_for_setup(setup_id, product_id)

    def add_columns_from_names(
        self, product_id: int, column_names: List[str], acting_user: User
    ) -> List[TemplateColumnResponse]:
        """Bulk-add new String-typed custom columns detected from an Excel import, skipping any that already exist."""
        created: List[TemplateColumnResponse] = []
        for raw_name in column_names:
            normalized_name = raw_name.strip().lower().replace(" ", "_")
            if not normalized_name or normalized_name in {c["name"] for c in MANDATORY_TEMPLATE_COLUMNS}:
                continue
            if self._template_repository.get_column_by_name(product_id, normalized_name) is not None:
                continue
            created.append(
                self.add_column(
                    product_id,
                    TemplateColumnCreateRequest(name=normalized_name, label=raw_name.strip(), data_type=ColumnDataType.STRING),
                    acting_user,
                )
            )
        return created
