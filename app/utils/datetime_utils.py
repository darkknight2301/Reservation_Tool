"""Timezone-safe datetime helper functions used across services and utils."""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime (matches DB columns)."""
    return datetime.utcnow()


def to_iso(value: datetime) -> str:
    """Format a datetime as an ISO-8601 string, assuming UTC if naive."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
