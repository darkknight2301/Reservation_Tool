"""FastAPI application factory and entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger
from app.db.session import enable_sqlite_foreign_keys
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.scheduler_service import shutdown_scheduler, start_scheduler
from app.web.deps import ForbiddenWebError, RedirectToLogin, templates
from app.web.routers.announcements_view import router as announcements_web_router
from app.web.routers.audit_view import router as audit_web_router
from app.web.routers.auth_view import router as auth_web_router
from app.web.routers.dashboard_view import router as dashboard_web_router
from app.web.routers.developer_logs_view import router as developer_logs_web_router
from app.web.routers.docs_view import router as docs_web_router
from app.web.routers.groups_view import router as groups_web_router
from app.web.routers.products_view import router as products_web_router
from app.web.routers.setups_view import router as setups_web_router
from app.web.routers.swap_mapping_view import router as swap_mapping_web_router
from app.web.routers.users_view import router as users_web_router

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.APP_DEBUG,
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)

    @app.exception_handler(RedirectToLogin)
    async def handle_redirect_to_login(request: Request, exc: RedirectToLogin) -> RedirectResponse:
        """A web page's auth dependency failed: send the browser to /login."""
        return RedirectResponse(url="/login", status_code=302)

    @app.exception_handler(ForbiddenWebError)
    async def handle_forbidden_web(request: Request, exc: ForbiddenWebError):
        """A web page's permission check failed: render a 403 page."""
        return templates.TemplateResponse(
            "errors/403.html", {"request": request, "current_user": None, "message": exc.message}, status_code=403
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        """404s (and other raw HTTP errors) on non-API routes render an HTML page; API routes get JSON."""
        if request.url.path.startswith(settings.API_V1_PREFIX) or exc.status_code != 404:
            return _json_http_error(exc)
        return templates.TemplateResponse("errors/404.html", {"request": request, "current_user": None}, status_code=404)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_web_router)
    app.include_router(dashboard_web_router)
    app.include_router(products_web_router)
    app.include_router(groups_web_router)
    app.include_router(users_web_router)
    app.include_router(setups_web_router)
    app.include_router(swap_mapping_web_router)
    app.include_router(announcements_web_router)
    app.include_router(audit_web_router)
    app.include_router(developer_logs_web_router)
    app.include_router(docs_web_router)

    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

    @app.on_event("startup")
    def on_startup() -> None:
        enable_sqlite_foreign_keys()
        start_scheduler()
        logger.info("Application startup complete.")

    @app.on_event("shutdown")
    def on_shutdown() -> None:
        shutdown_scheduler()
        logger.info("Application shutdown complete.")

    @app.get("/health", tags=["Health"])
    def health_check() -> dict:
        """Liveness/readiness probe endpoint."""
        return {"status": "ok"}

    return app


def _json_http_error(exc: StarletteHTTPException):
    """Build a JSON error envelope for a raw Starlette HTTP exception (API routes, non-404s)."""
    from starlette.responses import JSONResponse

    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": exc.detail, "details": {}}})


app = create_app()
