"""Pydantic schemas for authentication endpoints."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials submitted to ``POST /auth/login``."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access + refresh token pair returned on successful login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload for ``POST /auth/refresh``."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Payload for ``POST /auth/logout``."""

    refresh_token: str
