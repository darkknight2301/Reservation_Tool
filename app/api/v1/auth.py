"""Authentication endpoints: register, login, refresh, logout, change password, forgot/reset password."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import get_auth_service, get_current_user
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.schemas.user import (
    ChangePasswordRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.models.user import User
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: UserRegisterRequest, request: Request, auth_service: AuthService = Depends(get_auth_service)) -> User:
    """Self-service registration. Account lands in PENDING status."""
    return auth_service.register(payload, ip_address=request.client.host if request.client else None)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    """Authenticate with username/password and receive an access/refresh token pair."""
    access_token, refresh_token = auth_service.authenticate(
        payload.username, payload.password, ip_address=request.client.host if request.client else None
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)) -> TokenResponse:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    access_token, refresh_token = auth_service.refresh(payload.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, auth_service: AuthService = Depends(get_auth_service)) -> MessageResponse:
    """Revoke a refresh token, ending that session."""
    auth_service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    """Change the current user's password, revoking all existing sessions."""
    auth_service.change_password(current_user, payload.current_password, payload.new_password)
    return MessageResponse(message="Password changed successfully.")


@router.post("/password-reset/request", response_model=MessageResponse)
def request_password_reset(
    payload: PasswordResetRequestRequest, request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> MessageResponse:
    """
    Request a password-reset email. Always returns the same message
    regardless of whether the address has an account, to avoid leaking
    which emails are registered.
    """
    auth_service.request_password_reset(
        payload.email, base_url=str(request.base_url), ip_address=request.client.host if request.client else None
    )
    return MessageResponse(message="If an account exists for that email, a password reset link has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest, request: Request, auth_service: AuthService = Depends(get_auth_service)
) -> MessageResponse:
    """Complete a password reset using the token emailed by ``/password-reset/request``."""
    auth_service.reset_password(
        payload.token, payload.new_password, ip_address=request.client.host if request.client else None
    )
    return MessageResponse(message="Password reset successfully. You can now log in with your new password.")
