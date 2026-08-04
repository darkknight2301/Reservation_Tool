"""Correlation-ID and access-log middleware."""
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import correlation_id_ctx_var, get_logger

logger = get_logger("app.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Assigns a correlation id to every request (reusing an inbound
    ``X-Request-ID`` header if present) and logs one structured access-log
    line per request with method, path, status code, and duration.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = correlation_id_ctx_var.set(correlation_id)
        start_time = time.monotonic()

        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx_var.reset(token)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = correlation_id
        logger.info(
            "{0} {1} -> {2} ({3}ms)".format(request.method, request.url.path, response.status_code, duration_ms),
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
