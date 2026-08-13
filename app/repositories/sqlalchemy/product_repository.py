"""SQLAlchemy implementation of the Product repository."""
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
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

    def delete(self, product_id: int) -> bool:
        """
        Delete a Product.

        Returns:
            True if the product was deleted (or did not exist). False if the
            delete was blocked by a foreign key constraint -- Setups (or
            template columns with dependent data) still reference it. This
            is a defense-in-depth safety net behind the application-level
            ``has_setups`` check in ``ProductService.delete``: it also
            catches the case where a Setup was assigned to the product in
            between that check and this delete.
        """
        product = self.get_by_id(product_id)
        if product is None:
            return True
        self._db.delete(product)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            return False
        return True

    def has_setups(self, product_id: int) -> bool:
        return self._db.query(Setup.id).filter(Setup.product_id == product_id).first() is not None
