"""User ORM model, including registration/approval workflow fields."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.constants import UserStatus
from app.db.base import Base


class User(Base):
    """
    A system user.

    New users register via ``POST /auth/register`` and land in
    ``UserStatus.PENDING``. A user with ``user:approve`` permission (LEAD,
    MANAGER, or OWNER) must approve the account before it can log in.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    status = Column(String(20), nullable=False, default=UserStatus.PENDING)
    is_active = Column(Boolean, nullable=False, default=True)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    role = relationship("Role", back_populates="users", foreign_keys=[role_id])
    group = relationship("Group", back_populates="users", foreign_keys=[group_id])
    groups = relationship("Group", secondary="user_groups", back_populates="members")
    approved_by = relationship("User", remote_side=[id], foreign_keys=[approved_by_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<User id={0} username={1} status={2}>".format(self.id, self.username, self.status)
