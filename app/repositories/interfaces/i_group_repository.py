"""Repository interface (Protocol) for the Group aggregate."""
from typing import List, Optional, Protocol, Tuple

from app.models.group import Group


class IGroupRepository(Protocol):
    """Persistence contract for Group entities."""

    def get_by_id(self, group_id: int) -> Optional[Group]:
        ...

    def get_by_name(self, name: str) -> Optional[Group]:
        ...

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Group], int]:
        ...

    def create(self, group: Group) -> Group:
        ...

    def update(self, group: Group) -> Group:
        ...

    def delete(self, group_id: int) -> None:
        ...

    def has_members_or_setups(self, group_id: int) -> bool:
        ...
