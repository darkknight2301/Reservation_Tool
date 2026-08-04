"""Audit log read-only endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_audit_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.audit_log import AuditLogFilter, AuditLogResponse
from app.schemas.common import PaginatedResponse
from app.services.audit_service import AuditService
from app.utils.pagination import total_pages

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
def list_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    _current_user: User = Depends(require_permission(PermissionCode.AUDIT_VIEW)),
    audit_service: AuditService = Depends(get_audit_service),
) -> PaginatedResponse:
    """List audit log entries with optional filters. Requires ``audit:view``."""
    filters = AuditLogFilter(entity_type=entity_type, entity_id=entity_id, user_id=user_id, action=action)
    items, total_items = audit_service.list(filters, page, page_size)
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, total_items=total_items, total_pages=total_pages(total_items, page_size)
    )
