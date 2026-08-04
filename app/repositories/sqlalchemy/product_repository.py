"""SQLAlchemy implementation of the Product repository."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.setup import Setup
from app.utils.pagination import paginate_query


class ProductRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IProductRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, product_id: int) -> Optional[Product]:
        return self._db.query(Product).filter(Product.id == product_id).first()

    def get_by_name(self, name: str) -> Optional[Product]:
        return self._db.query(Product).filter(Product.name == name).first()

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Product], int]:
        query = self._db.query(Product)
        if search:
            query = query.filter(Product.name.ilike("%{0}%".format(search)))
        query = query.order_by(Product.name.asc())
        return paginate_query(query, page, page_size)

    def create(self, product: Product) -> Product:
        self._db.add(product)
        self._db.flush()
        self._db.refresh(product)
        return product

    def update(self, product: Product) -> Product:
        self._db.add(product)
        self._db.flush()
        self._db.refresh(product)
        return product

    def delete(self, product_id: int) -> None:
        product = self.get_by_id(product_id)
        if product is not None:
            self._db.delete(product)
            self._db.flush()

    def has_setups(self, product_id: int) -> bool:
        return self._db.query(Setup.id).filter(Setup.product_id == product_id).first() is not None
