"""Product CRUD endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_product_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.product import ProductCreateRequest, ProductResponse, ProductUpdateRequest
from app.services.product_service import ProductService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse[ProductResponse])
def list_products(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    product_service: ProductService = Depends(get_product_service),
) -> PaginatedResponse:
    """List products. Requires ``product:view``."""
    items, total_items = product_service.list(page, page_size, search)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Create a Product. Requires ``product:manage``."""
    return product_service.create(payload, current_user)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    _current_user: User = Depends(require_permission(PermissionCode.PRODUCT_VIEW)),
    product_service: ProductService = Depends(get_product_service),
):
    """Fetch a single Product by id. Requires ``product:view``."""
    return product_service.get_by_id(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdateRequest,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Update a Product. Requires ``product:manage``."""
    return product_service.update(product_id, payload, current_user)


@router.delete("/{product_id}", response_model=MessageResponse)
def delete_product(
    product_id: int,
    current_user: User = Depends(require_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
) -> MessageResponse:
    """Delete a Product. Requires ``product:manage``."""
    product_service.delete(product_id, current_user)
    return MessageResponse(message="Product deleted successfully.")
