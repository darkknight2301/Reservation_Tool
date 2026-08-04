"""Common, reusable Pydantic schemas: pagination envelope and error envelope."""
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

DataT = TypeVar("DataT")


class PaginatedResponse(GenericModel, Generic[DataT]):
    """Standard envelope returned by every list endpoint."""

    items: List[DataT]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class ErrorDetail(BaseModel):
    """The ``error`` object nested inside every error response."""

    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error envelope returned by the global exception handler."""

    error: ErrorDetail


class PaginationParams(BaseModel):
    """Shared query-parameter model for paginated list endpoints."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)


class MessageResponse(BaseModel):
    """Simple acknowledgement response for actions with no resource body."""

    message: str
    detail: Optional[str] = None
