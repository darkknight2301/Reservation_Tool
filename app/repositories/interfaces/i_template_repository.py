"""Repository interface (Protocol) for ProductTemplateColumn and SetupCustomFieldValue."""
from typing import Dict, List, Optional, Protocol

from app.models.product_template_column import ProductTemplateColumn
from app.models.setup_custom_field_value import SetupCustomFieldValue


class ITemplateRepository(Protocol):
    """Persistence contract for a Product's dynamic template columns and Setup custom values."""

    def get_column_by_id(self, column_id: int) -> Optional[ProductTemplateColumn]:
        ...

    def get_column_by_name(self, product_id: int, name: str) -> Optional[ProductTemplateColumn]:
        ...

    def list_columns_for_product(self, product_id: int) -> List[ProductTemplateColumn]:
        ...

    def create_column(self, column: ProductTemplateColumn) -> ProductTemplateColumn:
        ...

    def update_column(self, column: ProductTemplateColumn) -> ProductTemplateColumn:
        ...

    def delete_column(self, column_id: int) -> None:
        ...

    def get_values_for_setup(self, setup_id: int) -> List[SetupCustomFieldValue]:
        ...

    def get_values_for_setups(self, setup_ids: List[int]) -> Dict[int, List[SetupCustomFieldValue]]:
        ...

    def upsert_value(self, setup_id: int, template_column_id: int, value: Optional[str]) -> SetupCustomFieldValue:
        ...
