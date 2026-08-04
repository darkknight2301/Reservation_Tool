"""
RefreshToken ORM model.

Refresh tokens are tracked server-side (by JWT ``jti``) so that logout and
account deactivation can revoke them immediately, and so each refresh token
can be enforced as single-use (rotated on every use) to limit replay risk.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class RefreshToken(Base):
    """Server-side record of an issued refresh token."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(36), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<RefreshToken jti={0} user_id={1} revoked={2}>".format(self.jti, self.user_id, self.revoked)
