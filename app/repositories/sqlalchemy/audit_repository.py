"""SQLAlchemy implementation of the AuditLog repository (insert + read only)."""
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogFilter
from app.utils.pagination import paginate_query


class AuditLogRepository:
    """
    Concrete, SQLAlchemy-backed implementation of ``IAuditLogRepository``.

    Deliberately exposes no ``update``/``delete`` methods: the audit trail
    is append-only by construction, not merely by convention.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, audit_log: AuditLog) -> AuditLog:
        self._db.add(audit_log)
        self._db.flush()
        self._db.refresh(audit_log)
        return audit_log

    def list(self, filters: AuditLogFilter, page: int, page_size: int) -> Tuple[List[AuditLog], int]:
        query = self._db.query(AuditLog)
        if filters.entity_type:
            query = query.filter(AuditLog.entity_type == filters.entity_type)
        if filters.entity_id is not None:
            query = query.filter(AuditLog.entity_id == filters.entity_id)
        if filters.user_id is not None:
            query = query.filter(AuditLog.user_id == filters.user_id)
        if filters.action:
            query = query.filter(AuditLog.action == filters.action)
        query = query.order_by(AuditLog.created_at.desc())
        return paginate_query(query, page, page_size)
