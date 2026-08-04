"""
Security primitives: password hashing (bcrypt via passlib) and JWT
encode/decode (python-jose). Kept isolated from business logic so the
hashing scheme or token library can be swapped without touching services.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return _pwd_context.verify(plain_password, password_hash)


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Build and sign a JWT with standard claims plus any extra claims."""
    now = datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """Create a short-lived access token carrying the user id and role."""
    claims: Dict[str, Any] = {"role": role}
    if extra_claims:
        claims.update(extra_claims)
    return _create_token(
        subject=str(user_id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims=claims,
    )


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived refresh token carrying only the user id."""
    return _create_token(
        subject=str(user_id),
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT, verifying signature, expiry, and token type.

    Raises:
        AuthenticationError: if the token is malformed, expired, or of the
            wrong type.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Could not validate credentials.") from exc

    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type.")

    return payload
