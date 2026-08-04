"""
Application (operational) logging configuration.

This is intentionally separate from the domain audit trail (see
``app.models.audit_log`` / ``app.services.audit_service``). This module
configures Python's standard ``logging`` package to emit structured JSON
lines to a rotating file and to stdout (for systemd/journald capture),
including a per-request correlation id bound via a ``contextvars`` context
variable set by ``app.middleware.request_logging``.
"""
import json
import logging
import logging.config
import os
from contextvars import ContextVar
from typing import Any, Dict

from app.core.config import settings

# Bound by the request-logging middleware at the start of every request and
# read here so every log record emitted during that request carries it.
correlation_id_ctx_var: "ContextVar[str]" = ContextVar("correlation_id", default="-")


class CorrelationIdFilter(logging.Filter):
    """Injects the current request's correlation id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_ctx_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        for extra_key in ("user_id", "path", "method", "status_code", "duration_ms"):
            if hasattr(record, extra_key):
                payload[extra_key] = getattr(record, extra_key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Apply the dictConfig-based logging setup. Call once at app startup."""
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(settings.LOG_DIR, "app.log")

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {"()": CorrelationIdFilter},
        },
        "formatters": {
            "json": {"()": JsonFormatter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["correlation_id"],
                "level": settings.LOG_LEVEL,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filters": ["correlation_id"],
                "level": settings.LOG_LEVEL,
                "filename": log_file_path,
                "maxBytes": settings.LOG_FILE_MAX_BYTES,
                "backupCount": settings.LOG_FILE_BACKUP_COUNT,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": settings.LOG_LEVEL,
            "handlers": ["console", "file"],
        },
        "loggers": {
            "uvicorn": {"level": settings.LOG_LEVEL, "handlers": ["console", "file"], "propagate": False},
            "uvicorn.access": {"level": settings.LOG_LEVEL, "handlers": ["console", "file"], "propagate": False},
            "sqlalchemy.engine": {
                "level": "INFO" if settings.DATABASE_ECHO else "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger; a thin wrapper so callers don't import logging directly."""
    return logging.getLogger(name)
