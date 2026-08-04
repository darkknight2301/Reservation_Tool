"""Repository interface (Protocol) for the Setup aggregate."""
from typing import List, Optional, Protocol, Tuple

from app.models.setup import Setup
from app.schemas.setup import SetupFilter


class ISetupRepository(Protocol):
    """Persistence contract for Setup entities."""

    def get_by_id(self, setup_id: int) -> Optional[Setup]:
        ...

    def get_by_ip_or_hostname(self, ip_address: str, hostname: str) -> Optional[Setup]:
        ...

    def list(self, filters: SetupFilter, page: int, page_size: int) -> Tuple[List[Setup], int]:
        ...

    def list_all(self, filters: SetupFilter) -> List[Setup]:
        ...

    def create(self, setup: Setup) -> Setup:
        ...

    def update(self, setup: Setup) -> Setup:
        ...

    def update_status(self, setup_id: int, status: str) -> None:
        ...

    def delete(self, setup_id: int) -> None:
        ...

    def get_by_product_id(self, product_id: int) -> List[Setup]:
        ...
