"""SQLAlchemy implementation of the PasswordResetToken repository."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken


class PasswordResetRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IPasswordResetRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        self._db.add(reset_token)
        self._db.flush()
        self._db.refresh(reset_token)
        return reset_token

    def get_valid_by_token(self, token: str) -> Optional[PasswordResetToken]:
        return (
            self._db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token == token,
                PasswordResetToken.used.is_(False),
                PasswordResetToken.expires_at > datetime.utcnow(),
            )
            .first()
        )

    def mark_used(self, reset_token: PasswordResetToken) -> None:
        reset_token.used = True
        self._db.add(reset_token)
        self._db.flush()

    def invalidate_all_for_user(self, user_id: int) -> None:
        self._db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id, PasswordResetToken.used.is_(False)
        ).update({"used": True}, synchronize_session=False)
        self._db.flush()
