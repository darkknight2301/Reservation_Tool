"""
Web-layer dependencies.

The server-rendered UI authenticates via an HttpOnly cookie (``access_token``)
rather than an ``Authorization`` header, per the architecture document
(section 6). These dependencies mirror ``app.api.deps`` but redirect to
``/login`` (or render a 403 page) instead of returning a JSON error, since a
browser navigation expects HTML, not an error envelope.
"""
from typing import Callable, Optional

from fastapi import Cookie, Depends, Request
from fastapi.templating import Jinja2Templates

from app.api.deps import get_role_lookup_service, get_user_repository
from app.core.exceptions import AuthenticationError
from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.models.user import User
from app.repositories.sqlalchemy.user_repository import UserRepository
from app.services.role_lookup_service import RoleLookupService

templates = Jinja2Templates(directory="app/web/templates")


class RedirectToLogin(Exception):
    """Raised by web auth dependencies; translated to a redirect by main.py's handler."""


class ForbiddenWebError(Exception):
    """Raised by web permission dependencies; translated to a 403 page by main.py's handler."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def get_current_web_user(
    request: Request,
    access_token: Optional[str] = Cookie(default=None),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Resolve the current user from the ``access_token`` cookie.

    Raises:
        RedirectToLogin: if the cookie is missing/invalid/expired, or the
            account is no longer active -- the browser should be sent back
            to the login page.
    """
    if not access_token:
        raise RedirectToLogin()
    try:
        payload = decode_token(access_token, expected_type=TOKEN_TYPE_ACCESS)
    except AuthenticationError:
        raise RedirectToLogin()

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise RedirectToLogin()

    user = user_repository.get_by_id(int(user_id_raw))
    if user is None or not user.is_active:
        raise RedirectToLogin()

    return user


def get_optional_web_user(
    request: Request,
    access_token: Optional[str] = Cookie(default=None),
    user_repository: UserRepository = Depends(get_user_repository),
) -> Optional[User]:
    """Same as ``get_current_web_user`` but returns None instead of redirecting (for public pages)."""
    try:
        return get_current_web_user(request, access_token, user_repository)
    except RedirectToLogin:
        return None


def get_permission_codes(user: User) -> list:
    """Return the list of permission codes carried by the user's role (for template context)."""
    return [permission.code for permission in user.role.permissions]


def base_context(request: Request, current_user: Optional[User]) -> dict:
    """Common template context injected on every page: request, current_user, permissions."""
    return {
        "request": request,
        "current_user": current_user,
        "current_user_permissions": get_permission_codes(current_user) if current_user else [],
    }
    """Dependency factory: like ``require_permission`` but raises ForbiddenWebError (renders a 403 page)."""

    def _check(
        current_user: User = Depends(get_current_web_user),
        role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
    ) -> User:
        if not role_lookup_service.role_has_permission(current_user.role, permission_code):
            raise ForbiddenWebError("You do not have permission to view this page.")
        return current_user

    return _check
