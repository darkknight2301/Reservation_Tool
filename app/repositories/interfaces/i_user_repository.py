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
