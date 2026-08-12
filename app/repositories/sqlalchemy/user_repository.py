"""SQLAlchemy implementation of the User repository."""
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.group import Group
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserFilter
from app.utils.pagination import paginate_query


class UserRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IUserRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self._db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self._db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self._db.query(User).filter(User.email == email).first()

    def list(self, filters: UserFilter, page: int, page_size: int) -> Tuple[List[User], int]:
        query = self._db.query(User).join(Role, User.role_id == Role.id)

        if filters.status:
            query = query.filter(User.status == filters.status)
        if filters.role_name:
            query = query.filter(Role.name == filters.role_name)
        if filters.group_id is not None:
            query = query.filter(User.group_id == filters.group_id)
        if filters.search:
            like_pattern = "%{0}%".format(filters.search)
            query = query.filter(
                or_(
                    User.username.ilike(like_pattern),
                    User.email.ilike(like_pattern),
                    User.full_name.ilike(like_pattern),
                )
            )

        query = query.order_by(User.created_at.desc())
        return paginate_query(query, page, page_size)

    def create(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        self._db.refresh(user)
        return user

    def update(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        self._db.refresh(user)
        return user

    def delete(self, user_id: int) -> bool:
        """
        Permanently delete a user.

        Returns:
            True if the user was deleted (or did not exist). False if the
            delete was blocked by a foreign key constraint (the user still
            has reservations, swap requests, announcements, or export logs
            referencing them) -- the caller should fall back to deactivation.
        """
        user = self.get_by_id(user_id)
        if user is None:
            return True
        self._db.delete(user)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            return False
        return True

    def set_groups(self, user: User, group_ids: List[int]) -> User:
        """Replace a user's group memberships (the many-to-many ``groups`` set) with exactly the given ids."""
        if group_ids:
            groups = self._db.query(Group).filter(Group.id.in_(group_ids)).all()
        else:
            groups = []
        user.groups = groups
        self._db.add(user)
        self._db.flush()
        self._db.refresh(user)
        return user
