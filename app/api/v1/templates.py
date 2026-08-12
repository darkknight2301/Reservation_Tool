"""Product template ("Design Template") endpoints: custom column CRUD + reorder."""
from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_template_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.template import (
    ProductTemplateResponse,
    TemplateColumnCreateRequest,
    TemplateColumnReorderRequest,
    TemplateColumnResponse,
    TemplateColumnUpdateRequest,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/products/{product_id}/template", tags=["Product Template"])


@router.get("", response_model=ProductTemplateResponse)
def get_product_template(
    product_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    template_service: TemplateService = Depends(get_template_service),
) -> ProductTemplateResponse:
    """Fetch the full template (mandatory + custom columns) for a Product. Requires ``product:view``."""
    return template_service.get_template(product_id)


@router.post("/columns", response_model=TemplateColumnResponse, status_code=201)
def add_template_column(
    product_id: int,
    payload: TemplateColumnCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateColumnResponse:
    """Add a custom column to a Product's template. Requires ``product:manage``."""
    return template_service.add_column(product_id, payload, current_user)


@router.patch("/columns/{column_id}", response_model=TemplateColumnResponse)
def update_template_column(
    product_id: int,
    column_id: int,
    payload: TemplateColumnUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
) -> TemplateColumnResponse:
    """Edit a custom column (mandatory columns cannot be targeted). Requires ``product:manage``."""
    return template_service.update_column(product_id, column_id, payload, current_user)


@router.delete("/columns/{column_id}", response_model=MessageResponse)
def delete_template_column(
    product_id: int,
    column_id: int,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
) -> MessageResponse:
    """Delete a custom column (mandatory columns cannot be targeted). Requires ``product:manage``."""
    template_service.delete_column(product_id, column_id, current_user)
    return MessageResponse(message="Column deleted successfully.")


@router.post("/columns/reorder", response_model=List[TemplateColumnResponse])
def reorder_template_columns(
    product_id: int,
    payload: TemplateColumnReorderRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
) -> List[TemplateColumnResponse]:
    """Reorder a Product's custom columns. Requires ``product:manage``."""
    return template_service.reorder_columns(product_id, payload.column_ids, current_user)
