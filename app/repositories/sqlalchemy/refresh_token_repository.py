"""SQLAlchemy implementation of the RefreshToken repository."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IRefreshTokenRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        return self._db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    def create(self, refresh_token: RefreshToken) -> RefreshToken:
        self._db.add(refresh_token)
        self._db.flush()
        self._db.refresh(refresh_token)
        return refresh_token

    def revoke(self, jti: str) -> None:
        token = self.get_by_jti(jti)
        if token is not None:
            token.revoked = True
            self._db.add(token)
            self._db.flush()

    def revoke_all_for_user(self, user_id: int) -> None:
        self._db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)).update(
            {"revoked": True}, synchronize_session=False
        )
        self._db.flush()
