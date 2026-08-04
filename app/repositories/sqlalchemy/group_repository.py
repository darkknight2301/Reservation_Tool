"""SQLAlchemy implementation of the Group repository."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.group import Group
from app.models.setup import Setup
from app.models.user import User
from app.utils.pagination import paginate_query


class GroupRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IGroupRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, group_id: int) -> Optional[Group]:
        return self._db.query(Group).filter(Group.id == group_id).first()

    def get_by_name(self, name: str) -> Optional[Group]:
        return self._db.query(Group).filter(Group.name == name).first()

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Group], int]:
        query = self._db.query(Group)
        if search:
            query = query.filter(Group.name.ilike("%{0}%".format(search)))
        query = query.order_by(Group.name.asc())
        return paginate_query(query, page, page_size)

    def create(self, group: Group) -> Group:
        self._db.add(group)
        self._db.flush()
        self._db.refresh(group)
        return group

    def update(self, group: Group) -> Group:
        self._db.add(group)
        self._db.flush()
        self._db.refresh(group)
        return group

    def delete(self, group_id: int) -> None:
        group = self.get_by_id(group_id)
        if group is not None:
            self._db.delete(group)
            self._db.flush()

    def has_members_or_setups(self, group_id: int) -> bool:
        has_users = self._db.query(User.id).filter(User.group_id == group_id).first() is not None
        has_setups = self._db.query(Setup.id).filter(Setup.group_id == group_id).first() is not None
        return has_users or has_setups
