"""Pydantic schemas for Excel export/import operations."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.core.constants import ExportType


class ExportLogResponse(BaseModel):
    """Read model for an ExportLog entry."""

    id: int
    user_id: int
    export_type: str
    file_path: str
    filters: Optional[str] = None
    row_count: int
    created_at: datetime

    class Config:
        orm_mode = True


class ImportRowError(BaseModel):
    """A single row-level validation error surfaced from an import attempt."""

    row: int
    field: Optional[str] = None
    message: str


class ImportResultResponse(BaseModel):
    """Result summary returned after processing an Excel import upload."""

    batch_id: str
    entity_type: str
    total_rows: int
    created_count: int
    updated_count: int
    error_count: int
    errors: List[ImportRowError] = []
    committed: bool
    # Populated only by the product-template-aware import flow: Excel columns
    # found in the workbook that are not yet part of the product's template.
    # When non-empty and ``committed`` is False, the caller must explicitly
    # accept (or reject) adding these columns before the import can proceed.
    new_columns: List[str] = []


class SetupExportFilter(BaseModel):
    """Filter parameters accepted by the Setup export endpoint."""

    product_id: Optional[int] = None
    group_id: Optional[int] = None
    status: Optional[str] = None
    location: Optional[str] = None


class ReservationExportFilter(BaseModel):
    """Filter parameters accepted by the Reservation export endpoint."""

    user_id: Optional[int] = None
    setup_id: Optional[int] = None
    status: Optional[str] = None


__all__ = [
    "ExportLogResponse",
    "ImportRowError",
    "ImportResultResponse",
    "SetupExportFilter",
    "ReservationExportFilter",
    "ExportType",
]
