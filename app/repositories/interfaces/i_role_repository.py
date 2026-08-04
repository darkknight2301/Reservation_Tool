"""Repository interface (Protocol) for the Role aggregate."""
from typing import List, Optional, Protocol

from app.models.role import Role


class IRoleRepository(Protocol):
    """Persistence contract for Role entities."""

    def get_by_id(self, role_id: int) -> Optional[Role]:
        ...

    def get_by_name(self, name: str) -> Optional[Role]:
        ...

    def list_all(self) -> List[Role]:
        ...
