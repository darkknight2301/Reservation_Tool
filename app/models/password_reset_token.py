"""
PasswordResetToken ORM model.

A short-lived, single-use, cryptographically random token issued when a
user requests a password reset ("forgot password"). Tracked server-side
(mirroring how ``RefreshToken`` is tracked) so a token can be marked used
immediately after it resets a password, and so requesting a new reset
invalidates any earlier, still-pending one for that user.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class PasswordResetToken(Base):
    """Server-side record of an issued password-reset token."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    used = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<PasswordResetToken user_id={0} used={1}>".format(self.user_id, self.used)
