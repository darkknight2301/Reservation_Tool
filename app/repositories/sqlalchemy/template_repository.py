"""SQLAlchemy implementation of the template-column / custom-value repository."""
from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.product_template_column import ProductTemplateColumn
from app.models.setup_custom_field_value import SetupCustomFieldValue


class TemplateRepository:
    """Concrete, SQLAlchemy-backed implementation of ``ITemplateRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # --- ProductTemplateColumn -------------------------------------------------

    def get_column_by_id(self, column_id: int) -> Optional[ProductTemplateColumn]:
        return self._db.query(ProductTemplateColumn).filter(ProductTemplateColumn.id == column_id).first()

    def get_column_by_name(self, product_id: int, name: str) -> Optional[ProductTemplateColumn]:
        return (
            self._db.query(ProductTemplateColumn)
            .filter(ProductTemplateColumn.product_id == product_id, ProductTemplateColumn.name == name)
            .first()
        )

    def list_columns_for_product(self, product_id: int) -> List[ProductTemplateColumn]:
        return (
            self._db.query(ProductTemplateColumn)
            .filter(ProductTemplateColumn.product_id == product_id)
            .order_by(ProductTemplateColumn.order_index.asc(), ProductTemplateColumn.id.asc())
            .all()
        )

    def create_column(self, column: ProductTemplateColumn) -> ProductTemplateColumn:
        self._db.add(column)
        self._db.flush()
        self._db.refresh(column)
        return column

    def update_column(self, column: ProductTemplateColumn) -> ProductTemplateColumn:
        self._db.add(column)
        self._db.flush()
        self._db.refresh(column)
        return column

    def delete_column(self, column_id: int) -> None:
        column = self.get_column_by_id(column_id)
        if column is not None:
            self._db.delete(column)
            self._db.flush()

    # --- SetupCustomFieldValue --------------------------------------------------

    def get_values_for_setup(self, setup_id: int) -> List[SetupCustomFieldValue]:
        return (
            self._db.query(SetupCustomFieldValue)
            .filter(SetupCustomFieldValue.setup_id == setup_id)
            .all()
        )

    def get_values_for_setups(self, setup_ids: List[int]) -> Dict[int, List[SetupCustomFieldValue]]:
        if not setup_ids:
            return {}
        rows = (
            self._db.query(SetupCustomFieldValue)
            .filter(SetupCustomFieldValue.setup_id.in_(setup_ids))
            .all()
        )
        grouped: Dict[int, List[SetupCustomFieldValue]] = defaultdict(list)
        for row in rows:
            grouped[row.setup_id].append(row)
        return dict(grouped)

    def upsert_value(self, setup_id: int, template_column_id: int, value: Optional[str]) -> SetupCustomFieldValue:
        existing = (
            self._db.query(SetupCustomFieldValue)
            .filter(
                SetupCustomFieldValue.setup_id == setup_id,
                SetupCustomFieldValue.template_column_id == template_column_id,
            )
            .first()
        )
        if existing is not None:
            existing.value = value
            self._db.add(existing)
            self._db.flush()
            self._db.refresh(existing)
            return existing

        created = SetupCustomFieldValue(setup_id=setup_id, template_column_id=template_column_id, value=value)
        self._db.add(created)
        self._db.flush()
        self._db.refresh(created)
        return created
