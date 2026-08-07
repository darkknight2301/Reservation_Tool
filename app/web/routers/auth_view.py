"""Auth screens: login, register, logout. Sets/clears HttpOnly cookies for the web session."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.api.deps import get_auth_service
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.auth import LoginRequest
from app.schemas.user import UserRegisterRequest
from app.services.auth_service import AuthService
from app.web.deps import get_optional_web_user, templates

router = APIRouter(tags=["Web - Auth"])

_ACCESS_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
_REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _set_auth_cookies(response: RedirectResponse, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly, Secure, SameSite=Strict cookies for the web session."""
    response.set_cookie(
        "access_token", access_token, max_age=_ACCESS_COOKIE_MAX_AGE, httponly=True, samesite="strict", secure=not settings.APP_DEBUG
    )
    response.set_cookie(
        "refresh_token", refresh_token, max_age=_REFRESH_COOKIE_MAX_AGE, httponly=True, samesite="strict", secure=not settings.APP_DEBUG
    )


@router.get("/login")
def login_page(request: Request, current_user=Depends(get_optional_web_user)):
    """Render the login screen. Redirects to the dashboard if already logged in."""
    if current_user is not None:
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("auth/login.html", {"request": request, "current_user": None, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Process the login form; on success, sets cookies and redirects to the dashboard."""
    try:
        access_token, refresh_token = auth_service.authenticate(
            username, password, ip_address=request.client.host if request.client else None
        )
    except AppError as exc:
        return templates.TemplateResponse(
            "auth/login.html", {"request": request, "current_user": None, "error": exc.message}, status_code=exc.status_code
        )

    response = RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.get("/register")
def register_page(request: Request, current_user=Depends(get_optional_web_user)):
    """Render the self-service registration screen."""
    if current_user is not None:
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "current_user": None, "error": None, "success": None}
    )


@router.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Process the registration form. Account lands in PENDING status awaiting approval."""
    try:
        payload = UserRegisterRequest(username=username, email=email, password=password, full_name=full_name)
        auth_service.register(payload, ip_address=request.client.host if request.client else None)
    except AppError as exc:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "current_user": None, "error": exc.message, "success": None},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "auth/register.html", {"request": request, "current_user": None, "error": str(exc), "success": None}, status_code=422
        )

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "current_user": None,
            "error": None,
            "success": "Registration submitted. An administrator must approve your account before you can log in.",
        },
    )


@router.post("/logout")
def logout_submit(request: Request):
    """Clear the session cookies and return to the login screen."""
    response = RedirectResponse("/login", status_code=HTTP_302_FOUND)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
