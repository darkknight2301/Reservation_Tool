"""Role ORM model (RBAC)."""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Role(Base):
    """A named role (e.g. OWNER, LEAD) granting a fixed set of permissions."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )
    users = relationship("User", back_populates="role")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Role id={0} name={1}>".format(self.id, self.name)
