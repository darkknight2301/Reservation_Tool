"""Pydantic schemas for the dynamic product template ("Design Template") feature."""
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import ColumnDataType


class TemplateColumnCreateRequest(BaseModel):
    """Payload for adding a custom column to a Product's template."""

    name: str = Field(..., min_length=1, max_length=100)
    label: Optional[str] = Field(default=None, max_length=150)
    data_type: str = Field(default=ColumnDataType.STRING)
    required: bool = False
    default_value: Optional[str] = Field(default=None, max_length=500)
    allowed_values: Optional[List[str]] = None

    @validator("data_type")
    def _validate_data_type(cls, value: str) -> str:  # noqa: N805
        if value not in ColumnDataType.ALL:
            raise ValueError("data_type must be one of: {0}".format(", ".join(ColumnDataType.ALL)))
        return value

    @validator("allowed_values")
    def _validate_allowed_values(cls, value: Optional[List[str]], values: Dict[str, Any]) -> Optional[List[str]]:  # noqa: N805
        if values.get("data_type") == ColumnDataType.DROPDOWN and not value:
            raise ValueError("allowed_values is required for a Dropdown column.")
        return value


class TemplateColumnUpdateRequest(BaseModel):
    """Payload for editing an existing custom column. Mandatory columns can never be targeted."""

    label: Optional[str] = Field(default=None, max_length=150)
    required: Optional[bool] = None
    default_value: Optional[str] = Field(default=None, max_length=500)
    allowed_values: Optional[List[str]] = None


class TemplateColumnReorderRequest(BaseModel):
    """Payload for reordering a Product's custom columns."""

    column_ids: List[int] = Field(..., min_items=1)


class TemplateColumnResponse(BaseModel):
    """Read model for one custom template column."""

    id: int
    product_id: int
    name: str
    label: str
    data_type: str
    required: bool
    default_value: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    order_index: int
    mandatory: bool = False

    class Config:
        orm_mode = True

    @classmethod
    def from_orm_column(cls, column) -> "TemplateColumnResponse":
        allowed = json.loads(column.allowed_values) if column.allowed_values else None
        return cls(
            id=column.id,
            product_id=column.product_id,
            name=column.name,
            label=column.label,
            data_type=column.data_type,
            required=column.required,
            default_value=column.default_value,
            allowed_values=allowed,
            order_index=column.order_index,
            mandatory=False,
        )


class MandatoryColumnResponse(BaseModel):
    """Read model for one of the eight fixed, non-editable mandatory columns."""

    name: str
    label: str
    data_type: str = ColumnDataType.STRING
    required: bool = True
    mandatory: bool = True


class ProductTemplateResponse(BaseModel):
    """The full, ordered template for a Product: mandatory columns + custom columns."""

    product_id: int
    mandatory_columns: List[MandatoryColumnResponse]
    custom_columns: List[TemplateColumnResponse]


class DetectedColumnsResponse(BaseModel):
    """Result of comparing an uploaded Excel workbook's headers against a Product's template."""

    product_id: int
    known_columns: List[str]
    new_columns: List[str]
    total_rows: int


class SetupCustomFieldsResponse(BaseModel):
    """The custom-field values currently stored for one Setup, keyed by column name."""

    setup_id: int
    values: Dict[str, Any] = {}


class SetupCustomFieldsUpdateRequest(BaseModel):
    """Payload for setting a Setup's custom-field values, keyed by column name."""

    values: Dict[str, Any] = {}
