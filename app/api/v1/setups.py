"""Setup CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_setup_service, get_template_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.setup import SetupCreateRequest, SetupFilter, SetupResponse, SetupUpdateRequest
from app.schemas.template import SetupCustomFieldsResponse, SetupCustomFieldsUpdateRequest
from app.services.setup_service import SetupService
from app.services.template_service import TemplateService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/setups", tags=["Setups"])


@router.get("", response_model=PaginatedResponse[SetupResponse])
def list_setups(
    product_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    setup_service: SetupService = Depends(get_setup_service),
) -> PaginatedResponse:
    """List setups with optional filters. Requires ``product:view``."""
    filters = SetupFilter(
        product_id=product_id, group_id=group_id, status=status, location=location, owner_id=owner_id, search=search
    )
    items, total_items = setup_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=SetupResponse, status_code=201)
def create_setup(
    payload: SetupCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Create a Setup. Requires ``product:manage``."""
    return setup_service.create(payload, current_user)


@router.get("/{setup_id}", response_model=SetupResponse)
def get_setup(
    setup_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Fetch a single Setup by id. Requires ``product:view``."""
    return setup_service.get_by_id(setup_id)


@router.patch("/{setup_id}", response_model=SetupResponse)
def update_setup(
    setup_id: int,
    payload: SetupUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Update a Setup, including status transitions. Requires ``product:manage``."""
    return setup_service.update(setup_id, payload, current_user)


@router.delete("/{setup_id}", response_model=MessageResponse)
def delete_setup(
    setup_id: int,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
) -> MessageResponse:
    """Delete a Setup. Requires ``product:manage``."""
    setup_service.delete(setup_id, current_user)
    return MessageResponse(message="Setup deleted successfully.")


@router.get("/{setup_id}/custom-fields", response_model=SetupCustomFieldsResponse)
def get_setup_custom_fields(
    setup_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    setup_service: SetupService = Depends(get_setup_service),
    template_service: TemplateService = Depends(get_template_service),
) -> SetupCustomFieldsResponse:
    """Fetch a Setup's product-specific custom field values. Requires ``product:view``."""
    setup = setup_service.get_by_id(setup_id)
    values = template_service.get_values_map_for_setup(setup_id, setup.product_id)
    return SetupCustomFieldsResponse(setup_id=setup_id, values=values)


@router.put("/{setup_id}/custom-fields", response_model=SetupCustomFieldsResponse)
def set_setup_custom_fields(
    setup_id: int,
    payload: SetupCustomFieldsUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
    template_service: TemplateService = Depends(get_template_service),
) -> SetupCustomFieldsResponse:
    """Set a Setup's product-specific custom field values, validated against its Product's template. Requires ``product:manage``."""
    setup = setup_service.get_by_id(setup_id)
    values = template_service.set_setup_values(setup_id, setup.product_id, payload.values, current_user)
    return SetupCustomFieldsResponse(setup_id=setup_id, values=values)
