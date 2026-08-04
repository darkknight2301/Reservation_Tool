"""Repository interface (Protocol) for the RefreshToken aggregate."""
from typing import Optional, Protocol

from app.models.refresh_token import RefreshToken


class IRefreshTokenRepository(Protocol):
    """Persistence contract for server-side refresh token tracking."""

    def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        ...

    def create(self, refresh_token: RefreshToken) -> RefreshToken:
        ...

    def revoke(self, jti: str) -> None:
        ...

    def revoke_all_for_user(self, user_id: int) -> None:
        ...
