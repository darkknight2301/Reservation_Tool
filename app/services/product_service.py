"""Product service: business logic for Product CRUD."""
from typing import List, Optional, Tuple

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.product import Product
from app.models.user import User
from app.repositories.interfaces.i_product_repository import IProductRepository
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.services.audit_service import AuditService


class ProductService:
    """Business logic for Product CRUD."""

    def __init__(self, product_repository: IProductRepository, audit_service: AuditService) -> None:
        self._product_repository = product_repository
        self._audit_service = audit_service

    def get_by_id(self, product_id: int) -> Product:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Product with id {0} was not found.".format(product_id))
        return product

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Product], int]:
        return self._product_repository.list(page, page_size, search)

    def create(self, payload: ProductCreateRequest, acting_user: User) -> Product:
        if self._product_repository.get_by_name(payload.name) is not None:
            raise ConflictError("A product named '{0}' already exists.".format(payload.name))
        product = Product(name=payload.name, description=payload.description)
        created = self._product_repository.create(product)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="Product",
            entity_id=created.id,
            new_value={"name": created.name},
        )
        return created

    def update(self, product_id: int, payload: ProductUpdateRequest, acting_user: User) -> Product:
        product = self.get_by_id(product_id)
        old_value = {"name": product.name, "description": product.description}

        if payload.name is not None and payload.name != product.name:
            if self._product_repository.get_by_name(payload.name) is not None:
                raise ConflictError("A product named '{0}' already exists.".format(payload.name))
            product.name = payload.name
        if payload.description is not None:
            product.description = payload.description

        updated = self._product_repository.update(product)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="Product",
            entity_id=updated.id,
            old_value=old_value,
            new_value={"name": updated.name, "description": updated.description},
        )
        return updated

    def delete(self, product_id: int, acting_user: User) -> None:
        product = self.get_by_id(product_id)
        if self._product_repository.has_setups(product_id):
            raise ConflictError(
                "Product '{0}' cannot be deleted while setups are assigned to it.".format(product.name)
            )
        deleted = self._product_repository.delete(product_id)
        if not deleted:
            raise ConflictError(
                "Product '{0}' cannot be deleted while setups are assigned to it.".format(product.name)
            )
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="Product",
            entity_id=product_id,
        )
