"""Pydantic schemas for the admin-configurable approval-hierarchy graph (GroupHierarchyEdge)."""
from datetime import datetime

from pydantic import BaseModel, validator

from app.core.constants import ApprovalHierarchyScope


class GroupHierarchyEdgeCreateRequest(BaseModel):
    """
    Create one directed edge: ``parent_group_id`` manages/leads-over
    ``child_group_id`` for approval-routing purposes.

    ``scope`` controls which domain(s) this edge applies to -- see
    ``ApprovalHierarchyScope`` for why a Swap-only or Borrow-only edge can
    be necessary (the same two Groups may need one edge for each domain if
    an org's Swap and Borrow reporting lines genuinely differ).
    """

    parent_group_id: int
    child_group_id: int
    scope: str = ApprovalHierarchyScope.BOTH

    @validator("scope")
    def _validate_scope(cls, value: str) -> str:  # noqa: N805
        if value not in ApprovalHierarchyScope.ALL:
            raise ValueError("scope must be one of: {0}".format(", ".join(ApprovalHierarchyScope.ALL)))
        return value

    @validator("child_group_id")
    def _validate_no_self_loop(cls, value: int, values: dict) -> int:  # noqa: N805
        if value == values.get("parent_group_id"):
            raise ValueError("A group cannot be its own parent.")
        return value


class GroupHierarchyEdgeDeleteRequest(BaseModel):
    """Identify one edge to remove (all three fields, since (parent, child, scope) together are the edge's identity)."""

    parent_group_id: int
    child_group_id: int
    scope: str = ApprovalHierarchyScope.BOTH


class GroupHierarchyEdgeResponse(BaseModel):
    id: int
    parent_group_id: int
    child_group_id: int
    scope: str
    created_at: datetime

    class Config:
        orm_mode = True
