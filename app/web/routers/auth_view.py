"""Auth screens: login, register, logout. Sets/clears HttpOnly cookies for the web session."""
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.api.deps import get_auth_service, get_group_service
from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.auth import LoginRequest
from app.schemas.user import PasswordResetConfirmRequest, PasswordResetRequestRequest, UserRegisterRequest
from app.services.auth_service import AuthService
from app.services.group_service import GroupService
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
def register_page(
    request: Request,
    current_user=Depends(get_optional_web_user),
    group_service: GroupService = Depends(get_group_service),
):
    """Render the self-service registration screen."""
    if current_user is not None:
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    groups, _ = group_service.list(page=1, page_size=200)
    return templates.TemplateResponse(
        "auth/register.html", {"request": request, "current_user": None, "error": None, "success": None, "groups": groups}
    )


@router.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    group_ids: List[str] = Form(default=[]),
    auth_service: AuthService = Depends(get_auth_service),
    group_service: GroupService = Depends(get_group_service),
):
    """Process the registration form. Account lands in PENDING status awaiting approval."""
    try:
        payload = UserRegisterRequest(
            username=username, email=email, password=password, full_name=full_name,
            group_ids=[int(g) for g in group_ids if g],
        )
        auth_service.register(payload, ip_address=request.client.host if request.client else None)
    except AppError as exc:
        groups, _ = group_service.list(page=1, page_size=200)
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "current_user": None, "error": exc.message, "success": None, "groups": groups},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        groups, _ = group_service.list(page=1, page_size=200)
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "current_user": None, "error": str(exc), "success": None, "groups": groups},
            status_code=422,
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


@router.get("/forgot-password")
def forgot_password_page(request: Request, current_user=Depends(get_optional_web_user)):
    """Render the 'forgot password' request form."""
    if current_user is not None:
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse(
        "auth/forgot_password.html", {"request": request, "current_user": None, "error": None, "success": None}
    )


@router.post("/forgot-password")
def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Process the 'forgot password' form. Always shows the same success
    message, whether or not the email belongs to an account, so the form
    can't be used to discover which addresses are registered.
    """
    try:
        payload = PasswordResetRequestRequest(email=email)
        auth_service.request_password_reset(
            payload.email, base_url=str(request.base_url), ip_address=request.client.host if request.client else None
        )
    except AppError:
        pass  # deliberately swallowed -- see the generic message below
    except ValueError:
        pass  # an invalid email format is treated the same as an unknown one
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {
            "request": request, "current_user": None, "error": None,
            "success": "If an account exists for that email, a password reset link has been sent.",
        },
    )


@router.get("/reset-password")
def reset_password_page(request: Request, token: str, current_user=Depends(get_optional_web_user)):
    """Render the 'set a new password' form. The token is carried through as a hidden field."""
    if current_user is not None:
        return RedirectResponse("/dashboard", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse(
        "auth/reset_password.html", {"request": request, "current_user": None, "error": None, "token": token}
    )


@router.post("/reset-password")
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Process the 'set a new password' form and complete the reset."""
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "current_user": None, "error": "Passwords do not match.", "token": token},
            status_code=422,
        )
    try:
        payload = PasswordResetConfirmRequest(token=token, new_password=new_password)
        auth_service.reset_password(
            payload.token, payload.new_password, ip_address=request.client.host if request.client else None
        )
    except AppError as exc:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "current_user": None, "error": exc.message, "token": token},
            status_code=exc.status_code,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "current_user": None, "error": str(exc), "token": token},
            status_code=422,
        )

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request, "current_user": None, "error": None,
            "success": "Password reset successfully. You can now log in with your new password.",
        },
    )
