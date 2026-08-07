"""Logs Dashboard: read-only audit log viewer with filters and pagination."""
from typing import Optional

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_audit_service
from app.core.constants import AuditAction, PermissionCode
from app.models.user import User
from app.schemas.audit_log import AuditLogFilter
from app.services.audit_service import AuditService
from app.utils.pagination import total_pages as compute_total_pages
from app.web.deps import base_context, require_web_permission, templates

router = APIRouter(tags=["Web - Logs"])


def _load_logs_context(request: Request, filters: AuditLogFilter, page: int, page_size: int, current_user: User, audit_service: AuditService) -> dict:
    logs, total_items = audit_service.list(filters, page, page_size)
    context = base_context(request, current_user)
    context.update(
        {
            "logs": logs,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": compute_total_pages(total_items, page_size),
            "filters": filters,
        }
    )
    return context


@router.get("/admin/logs")
def logs_dashboard_page(
    request: Request,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(require_web_permission(PermissionCode.AUDIT_VIEW)),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Render the full Logs Dashboard screen."""
    filters = AuditLogFilter(entity_type=entity_type, entity_id=entity_id, user_id=user_id, action=action)
    context = _load_logs_context(request, filters, page, page_size, current_user, audit_service)
    context.update({"actions": [AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE, AuditAction.APPROVE,
                                AuditAction.REJECT, AuditAction.LOGIN, AuditAction.LOGIN_FAILED, AuditAction.LOGOUT,
                                AuditAction.CANCEL, AuditAction.SWAP, AuditAction.IMPORT, AuditAction.EXPORT]})
    return templates.TemplateResponse("admin/logs.html", context)


@router.get("/admin/logs/table")
def logs_table_partial(
    request: Request,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(require_web_permission(PermissionCode.AUDIT_VIEW)),
    audit_service: AuditService = Depends(get_audit_service),
):
    """HTMX partial: re-render the audit log table on filter/page change."""
    filters = AuditLogFilter(entity_type=entity_type, entity_id=entity_id, user_id=user_id, action=action)
    context = _load_logs_context(request, filters, page, page_size, current_user, audit_service)
    return templates.TemplateResponse("admin/_logs_list.html", context)
