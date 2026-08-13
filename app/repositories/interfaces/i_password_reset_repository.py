"""Repository interface (Protocol) for the PasswordResetToken aggregate."""
from typing import Optional, Protocol

from app.models.password_reset_token import PasswordResetToken


class IPasswordResetRepository(Protocol):
    """Persistence contract for server-side password-reset token tracking."""

    def create(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        ...

    def get_valid_by_token(self, token: str) -> Optional[PasswordResetToken]:
        ...

    def mark_used(self, reset_token: PasswordResetToken) -> None:
        ...

    def invalidate_all_for_user(self, user_id: int) -> None:
        ...
