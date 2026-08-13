"""Repository interface (Protocol) for the Product aggregate."""
from typing import List, Optional, Protocol, Tuple

from app.models.product import Product


class IProductRepository(Protocol):
    """Persistence contract for Product entities."""

    def get_by_id(self, product_id: int) -> Optional[Product]:
        ...

    def get_by_name(self, name: str) -> Optional[Product]:
        ...

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Product], int]:
        ...

    def create(self, product: Product) -> Product:
        ...

    def update(self, product: Product) -> Product:
        ...

    def delete(self, product_id: int) -> bool:
        ...

    def has_setups(self, product_id: int) -> bool:
        ...
