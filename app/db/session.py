"""
Database engine and session factory.

``DATABASE_URL`` is the single seam that lets this application move from
SQLite to PostgreSQL: SQLAlchemy dialect-detects from the URL scheme, and no
SQLite-only SQL is used anywhere in the models or repositories.
"""
from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # Required for SQLite when the same connection may be used across
    # threads (FastAPI's threaded dependency execution for sync endpoints).
    _connect_args = {"check_same_thread": False}

engine: Engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def enable_sqlite_foreign_keys() -> None:
    """
    SQLite does not enforce FOREIGN KEY constraints unless explicitly told
    to via a PRAGMA on every connection. PostgreSQL enforces FKs natively,
    so this is a no-op there.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
