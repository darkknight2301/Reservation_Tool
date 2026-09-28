"""
Approval-hierarchy graph admin endpoints.

Lets an admin (``group:manage``) configure the data-driven approval
hierarchy that Swap and Borrow approval routing reads (see
``ApprovalRoutingService``). This is the "registration/admin configuration"
support for the approval tree described in the business rules -- there is
no seeded/hardcoded example hierarchy anywhere; every edge is created
through this API (or directly in the database).
"""
from typing import List

from fastapi import APIRouter, Depends

from app.api.deps import get_group_hierarchy_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.group_hierarchy import (
    GroupHierarchyEdgeCreateRequest,
    GroupHierarchyEdgeDeleteRequest,
    GroupHierarchyEdgeResponse,
)
from app.services.group_hierarchy_service import GroupHierarchyService

router = APIRouter(prefix="/group-hierarchy", tags=["Approval Hierarchy"])


@router.get("", response_model=List[GroupHierarchyEdgeResponse])
def list_hierarchy_edges(
    _current_user: User = Depends(require_permission(PermissionCode.GROUP_VIEW)),
    service: GroupHierarchyService = Depends(get_group_hierarchy_service),
):
    """List every edge in the approval-hierarchy graph. Requires ``group:view``."""
    return service.list_edges()


@router.post("", response_model=GroupHierarchyEdgeResponse, status_code=201)
def create_hierarchy_edge(
    payload: GroupHierarchyEdgeCreateRequest,
    current_user: User = Depends(require_permission(PermissionCode.GROUP_MANAGE)),
    service: GroupHierarchyService = Depends(get_group_hierarchy_service),
):
    """Add one directed parent-manages-child edge, scoped to SWAP/BORROW/BOTH. Requires ``group:manage``."""
    return service.create_edge(payload.parent_group_id, payload.child_group_id, payload.scope, current_user)


@router.delete("", status_code=204)
def delete_hierarchy_edge(
    payload: GroupHierarchyEdgeDeleteRequest,
    current_user: User = Depends(require_permission(PermissionCode.GROUP_MANAGE)),
    service: GroupHierarchyService = Depends(get_group_hierarchy_service),
):
    """Remove one edge, identified by (parent_group_id, child_group_id, scope). Requires ``group:manage``."""
    service.delete_edge(payload.parent_group_id, payload.child_group_id, payload.scope, current_user)
