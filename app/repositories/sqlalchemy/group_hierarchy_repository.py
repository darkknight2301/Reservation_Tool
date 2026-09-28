"""SQLAlchemy implementation of the GroupHierarchyEdge repository."""
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import ApprovalHierarchyScope
from app.core.exceptions import ConflictError, ValidationAppError
from app.models.group_hierarchy_edge import GroupHierarchyEdge


class GroupHierarchyRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IGroupHierarchyRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_parent_group_ids(self, group_id: int, scope: Optional[str] = None) -> List[int]:
        query = self._db.query(GroupHierarchyEdge.parent_group_id).filter(
            GroupHierarchyEdge.child_group_id == group_id
        )
        if scope is not None:
            query = query.filter(GroupHierarchyEdge.scope.in_((scope, ApprovalHierarchyScope.BOTH)))
        return [row[0] for row in query.all()]

    def get_child_group_ids(self, group_id: int, scope: Optional[str] = None) -> List[int]:
        query = self._db.query(GroupHierarchyEdge.child_group_id).filter(
            GroupHierarchyEdge.parent_group_id == group_id
        )
        if scope is not None:
            query = query.filter(GroupHierarchyEdge.scope.in_((scope, ApprovalHierarchyScope.BOTH)))
        return [row[0] for row in query.all()]

    def list_all(self) -> List[GroupHierarchyEdge]:
        return self._db.query(GroupHierarchyEdge).order_by(GroupHierarchyEdge.id.asc()).all()

    def create_edge(self, parent_group_id: int, child_group_id: int, scope: str) -> GroupHierarchyEdge:
        if parent_group_id == child_group_id:
            raise ValidationAppError("A group cannot be its own parent in the approval hierarchy.")
        if scope not in ApprovalHierarchyScope.ALL:
            raise ValidationAppError("scope must be one of: {0}".format(", ".join(ApprovalHierarchyScope.ALL)))
        edge = GroupHierarchyEdge(parent_group_id=parent_group_id, child_group_id=child_group_id, scope=scope)
        self._db.add(edge)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            raise ConflictError("This hierarchy edge (for this scope) already exists.")
        self._db.refresh(edge)
        return edge

    def delete_edge(self, parent_group_id: int, child_group_id: int, scope: str) -> bool:
        edge = (
            self._db.query(GroupHierarchyEdge)
            .filter(
                GroupHierarchyEdge.parent_group_id == parent_group_id,
                GroupHierarchyEdge.child_group_id == child_group_id,
                GroupHierarchyEdge.scope == scope,
            )
            .first()
        )
        if edge is None:
            return False
        self._db.delete(edge)
        self._db.flush()
        return True
