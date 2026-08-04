"""
Audit service.

A thin write-through helper called by other services after any mutating
action, so nothing changes state without being recorded. Never called
directly by API routers.
"""
import json
from typing import Any, Dict, Optional, Tuple

from app.models.audit_log import AuditLog
from app.repositories.interfaces.i_audit_repository import IAuditLogRepository
from app.schemas.audit_log import AuditLogFilter


def _serialize(value: Optional[Dict[str, Any]]) -> Optional[str]:
    """JSON-encode a snapshot dict, or return None if no snapshot given."""
    if value is None:
        return None
    return json.dumps(value, default=str)


class AuditService:
    """Records audit trail entries for state-changing actions."""

    def __init__(self, audit_repository: IAuditLogRepository) -> None:
        self._audit_repository = audit_repository

    def record(
        self,
        user_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Persist one audit trail entry."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=_serialize(old_value),
            new_value=_serialize(new_value),
            ip_address=ip_address,
        )
        return self._audit_repository.create(audit_log)

    def list(self, filters: AuditLogFilter, page: int, page_size: int) -> Tuple[Any, int]:
        """List audit log entries matching the given filters, paginated."""
        return self._audit_repository.list(filters, page, page_size)
