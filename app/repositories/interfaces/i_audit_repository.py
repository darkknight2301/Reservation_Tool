"""Repository interface (Protocol) for the AuditLog aggregate (append-only)."""
from typing import List, Optional, Protocol, Tuple

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogFilter


class IAuditLogRepository(Protocol):
    """Persistence contract for AuditLog entries. Insert-only by design."""

    def create(self, audit_log: AuditLog) -> AuditLog:
        ...

    def list(self, filters: AuditLogFilter, page: int, page_size: int) -> Tuple[List[AuditLog], int]:
        ...
