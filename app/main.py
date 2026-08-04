"""FastAPI application factory and entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger
from app.db.session import enable_sqlite_foreign_keys
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.scheduler_service import shutdown_scheduler, start_scheduler

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

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

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


app = create_app()
