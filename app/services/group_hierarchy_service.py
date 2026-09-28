"""
Group hierarchy (approval-routing graph) admin service.

Lets an admin (``group:manage``) configure the data-driven approval
hierarchy that ``ApprovalRoutingService`` walks -- creating/removing edges
between Groups, scoped to SWAP, BORROW, or BOTH. This is the "registration/
admin configuration support" for the approval tree: no edge is ever
hardcoded, they are all rows an admin creates through this service (or
directly in the database/import tooling), exactly like every other
data-driven configuration in the system (RBAC's `role_permissions`, for
instance).
"""
from typing import List

from app.core.constants import ApprovalHierarchyScope, AuditAction
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.group_hierarchy_edge import GroupHierarchyEdge
from app.models.user import User
from app.repositories.interfaces.i_group_hierarchy_repository import IGroupHierarchyRepository
from app.repositories.interfaces.i_group_repository import IGroupRepository
from app.services.audit_service import AuditService


class GroupHierarchyService:
    """Business logic for admin-configuring the approval-hierarchy graph."""

    def __init__(
        self,
        group_hierarchy_repository: IGroupHierarchyRepository,
        group_repository: IGroupRepository,
        audit_service: AuditService,
    ) -> None:
        self._group_hierarchy_repository = group_hierarchy_repository
        self._group_repository = group_repository
        self._audit_service = audit_service

    def list_edges(self) -> List[GroupHierarchyEdge]:
        return self._group_hierarchy_repository.list_all()

    def create_edge(self, parent_group_id: int, child_group_id: int, scope: str, acting_user: User) -> GroupHierarchyEdge:
        if scope not in ApprovalHierarchyScope.ALL:
            raise ValidationAppError("scope must be one of: {0}".format(", ".join(ApprovalHierarchyScope.ALL)))
        if self._group_repository.get_by_id(parent_group_id) is None:
            raise NotFoundError("Group with id {0} was not found.".format(parent_group_id))
        if self._group_repository.get_by_id(child_group_id) is None:
            raise NotFoundError("Group with id {0} was not found.".format(child_group_id))

        edge = self._group_hierarchy_repository.create_edge(parent_group_id, child_group_id, scope)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="GroupHierarchyEdge",
            entity_id=edge.id,
            new_value={"parent_group_id": parent_group_id, "child_group_id": child_group_id, "scope": scope},
        )
        return edge

    def delete_edge(self, parent_group_id: int, child_group_id: int, scope: str, acting_user: User) -> None:
        deleted = self._group_hierarchy_repository.delete_edge(parent_group_id, child_group_id, scope)
        if not deleted:
            raise NotFoundError("No such hierarchy edge exists.")
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="GroupHierarchyEdge",
            entity_id=None,
            old_value={"parent_group_id": parent_group_id, "child_group_id": child_group_id, "scope": scope},
        )
