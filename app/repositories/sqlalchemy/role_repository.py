"""SQLAlchemy implementation of the Role repository."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.role import Role


class RoleRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IRoleRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, role_id: int) -> Optional[Role]:
        return self._db.query(Role).filter(Role.id == role_id).first()

    def get_by_name(self, name: str) -> Optional[Role]:
        return self._db.query(Role).filter(Role.name == name).first()

    def list_all(self) -> List[Role]:
        return self._db.query(Role).order_by(Role.name.asc()).all()
