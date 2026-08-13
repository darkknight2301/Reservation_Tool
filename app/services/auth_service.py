"""
Authentication service.

Handles self-service registration (landing in PENDING status), credential
verification and token issuance, refresh-token rotation, logout
(revocation), and the forgot/reset password flow. Immediate revocability is
achieved by re-fetching the user from the database on every authenticated
request (see ``app.api.deps``) rather than trusting JWT claims alone.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.core.config import settings
from app.core.constants import AuditAction, RoleName, UserStatus
from app.core.exceptions import (
    AccountDisabledError,
    AccountNotApprovedError,
    AuthenticationError,
    ConflictError,
)
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.interfaces.i_password_reset_repository import IPasswordResetRepository
from app.repositories.interfaces.i_refresh_token_repository import IRefreshTokenRepository
from app.repositories.interfaces.i_user_repository import IUserRepository
from app.schemas.user import UserRegisterRequest
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.role_lookup_service import RoleLookupService


class AuthService:
    """Coordinates registration, login, token refresh, logout, and password reset."""

    def __init__(
        self,
        user_repository: IUserRepository,
        refresh_token_repository: IRefreshTokenRepository,
        role_lookup_service: RoleLookupService,
        audit_service: AuditService,
        password_reset_repository: Optional[IPasswordResetRepository] = None,
        email_service: Optional[EmailService] = None,
    ) -> None:
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._role_lookup_service = role_lookup_service
        self._audit_service = audit_service
        self._password_reset_repository = password_reset_repository
        self._email_service = email_service

    def register(self, payload: UserRegisterRequest, ip_address: Optional[str] = None) -> User:
        """
        Register a new user account in PENDING status.

        Raises:
            ConflictError: if the username or email is already taken.
        """
        if self._user_repository.get_by_username(payload.username) is not None:
            raise ConflictError("Username is already taken.", details={"field": "username"})
        if self._user_repository.get_by_email(payload.email) is not None:
            raise ConflictError("Email is already registered.", details={"field": "email"})

        default_role = self._role_lookup_service.get_role_by_name(RoleName.USER)
        primary_group_id = payload.group_id
        if primary_group_id is None and payload.group_ids:
            primary_group_id = payload.group_ids[0]
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role_id=default_role.id,
            group_id=primary_group_id,
            status=UserStatus.PENDING,
            is_active=True,
        )
        created_user = self._user_repository.create(user)
        if payload.group_ids is not None:
            self._user_repository.set_groups(created_user, payload.group_ids)
        self._audit_service.record(
            user_id=None,
            action=AuditAction.CREATE,
            entity_type="User",
            entity_id=created_user.id,
            new_value={"username": created_user.username, "status": created_user.status},
            ip_address=ip_address,
        )
        return created_user

    def authenticate(self, username: str, password: str, ip_address: Optional[str] = None) -> Tuple[str, str]:
        """
        Verify credentials and issue an access/refresh token pair.

        Raises:
            AuthenticationError: invalid credentials.
            AccountNotApprovedError: registration still pending approval.
            AccountDisabledError: account has been disabled/rejected.
        """
        user = self._user_repository.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            self._audit_service.record(
                user_id=user.id if user else None,
                action=AuditAction.LOGIN_FAILED,
                entity_type="User",
                entity_id=user.id if user else None,
                ip_address=ip_address,
            )
            raise AuthenticationError("Invalid username or password.")

        if user.status == UserStatus.PENDING:
            raise AccountNotApprovedError("Your account is pending approval by a Lead or above.")
        if user.status in (UserStatus.REJECTED, UserStatus.DISABLED) or not user.is_active:
            raise AccountDisabledError("Your account is disabled. Contact an administrator.")

        access_token, refresh_token = self._issue_token_pair(user)
        self._audit_service.record(
            user_id=user.id,
            action=AuditAction.LOGIN,
            entity_type="User",
            entity_id=user.id,
            ip_address=ip_address,
        )
        return access_token, refresh_token

    def _issue_token_pair(self, user: User) -> Tuple[str, str]:
        """Create and persist a new access/refresh token pair for a user."""
        access_token = create_access_token(user_id=user.id, role=user.role.name)
        refresh_token = create_refresh_token(user_id=user.id)
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)

        self._refresh_token_repository.create(
            RefreshToken(
                jti=payload["jti"],
                user_id=user.id,
                revoked=False,
                expires_at=datetime.utcfromtimestamp(payload["exp"]),
            )
        )
        return access_token, refresh_token

    def refresh(self, refresh_token: str) -> Tuple[str, str]:
        """
        Exchange a valid, non-revoked refresh token for a new token pair.

        The presented refresh token is revoked immediately (single-use
        rotation) regardless of outcome, to limit replay risk.
        """
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        jti = payload["jti"]
        stored_token = self._refresh_token_repository.get_by_jti(jti)

        if stored_token is None or stored_token.revoked:
            raise AuthenticationError("Refresh token is invalid or has already been used.")
        if stored_token.expires_at < datetime.utcnow():
            raise AuthenticationError("Refresh token has expired.")

        self._refresh_token_repository.revoke(jti)

        user = self._user_repository.get_by_id(stored_token.user_id)
        if user is None or not user.is_active or user.status != UserStatus.APPROVED:
            raise AuthenticationError("Account is no longer active.")

        return self._issue_token_pair(user)

    def logout(self, refresh_token: str) -> None:
        """Revoke a refresh token, ending that session."""
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        self._refresh_token_repository.revoke(payload["jti"])

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Verify the current password and set a new one, revoking all sessions."""
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        self._user_repository.update(user)
        self._refresh_token_repository.revoke_all_for_user(user.id)
        self._audit_service.record(
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            new_value={"password_changed": True},
        )

    def request_password_reset(self, email: str, base_url: str, ip_address: Optional[str] = None) -> None:
        """
        Issue a password-reset token and email it, if -- and only if -- the
        address belongs to an active, approved account.

        Deliberately does not report whether the email was recognized, to
        avoid leaking which addresses have an account (the caller should
        always show the same "if an account exists..." message).
        """
        if self._password_reset_repository is None or self._email_service is None:
            raise AuthenticationError("Password reset is not configured.")

        user = self._user_repository.get_by_email(email)
        if user is None or not user.is_active or user.status != UserStatus.APPROVED:
            return

        self._password_reset_repository.invalidate_all_for_user(user.id)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
        self._password_reset_repository.create(
            PasswordResetToken(token=token, user_id=user.id, used=False, expires_at=expires_at)
        )

        reset_link = "{0}/reset-password?token={1}".format(base_url.rstrip("/"), token)
        self._email_service.send_email(
            to_addresses=[user.email],
            subject="{0}: Reset your password".format(settings.APP_NAME),
            body=(
                "Hi {0},\n\n"
                "We received a request to reset your {1} password. This link is valid for "
                "{2} minutes and can only be used once:\n\n{3}\n\n"
                "If you didn't request this, you can safely ignore this email -- your password "
                "will not be changed.\n"
            ).format(user.full_name, settings.APP_NAME, settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES, reset_link),
        )
        self._audit_service.record(
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            new_value={"password_reset_requested": True},
            ip_address=ip_address,
        )

    def reset_password(self, token: str, new_password: str, ip_address: Optional[str] = None) -> None:
        """
        Consume a password-reset token: set the new password, mark the token
        used (single-use), and revoke every existing session for the account.

        Raises:
            AuthenticationError: if the token is missing, already used, or expired.
        """
        if self._password_reset_repository is None:
            raise AuthenticationError("Password reset is not configured.")

        reset_token = self._password_reset_repository.get_valid_by_token(token)
        if reset_token is None:
            raise AuthenticationError("This password reset link is invalid or has expired.")

        user = self._user_repository.get_by_id(reset_token.user_id)
        if user is None or not user.is_active or user.status != UserStatus.APPROVED:
            raise AuthenticationError("This password reset link is invalid or has expired.")

        user.password_hash = hash_password(new_password)
        self._user_repository.update(user)
        self._password_reset_repository.mark_used(reset_token)
        self._refresh_token_repository.revoke_all_for_user(user.id)
        self._audit_service.record(
            user_id=user.id,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=user.id,
            new_value={"password_reset_completed": True},
            ip_address=ip_address,
        )
