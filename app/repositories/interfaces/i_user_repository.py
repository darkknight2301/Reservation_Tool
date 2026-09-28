"""Repository interface (Protocol) for the User aggregate."""
from typing import List, Optional, Protocol, Tuple

from app.models.user import User
from app.schemas.user import UserFilter


class IUserRepository(Protocol):
    """Persistence contract for User entities."""

    def get_by_id(self, user_id: int) -> Optional[User]:
        ...

    def get_by_username(self, username: str) -> Optional[User]:
        ...

    def get_by_email(self, email: str) -> Optional[User]:
        ...

    def list(self, filters: UserFilter, page: int, page_size: int) -> Tuple[List[User], int]:
        ...

    def create(self, user: User) -> User:
        ...

    def update(self, user: User) -> User:
        ...

    def delete(self, user_id: int) -> bool:
        ...

    def set_groups(self, user: User, group_ids: List[int]) -> User:
        ...

    def list_active_by_group_ids_and_roles(self, group_ids: List[int], role_names: List[str]) -> List[User]:
        """
        Every APPROVED, active User whose ``group_id`` is in ``group_ids`` AND
        whose Role name is in ``role_names``. Used by ``ApprovalRoutingService``
        to resolve "the Lead/Manager of Group X (or one of its ancestors)"
        without hardcoding any org chart -- who qualifies is entirely a
        function of existing User/Role/Group data.
        """
        ...
