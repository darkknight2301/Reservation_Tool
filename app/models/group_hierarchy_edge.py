"""
GroupHierarchyEdge ORM model.

A single directed "parent manages/leads child" edge between two Groups.
The full approval hierarchy (used to route Swap and Borrow approvals -- see
ARCHITECTURE_ASSESSMENT.md, "Open Questions" 1-3) is the set of these edges,
read and walked at request time by ``ApprovalRoutingService`` (Phase 3/4).

Modeled as a plain directed-edge table rather than a single
``parent_group_id`` column on ``Group`` because the business examples show
a child Group can have **more than one parent** (a DAG, not a strict tree --
e.g. Borrow example: "A -> D,E; B -> D,F,G" has D under both A and B).  A
single self-referential FK on ``Group`` cannot express that; an edge table
can, and also keeps the hierarchy fully data-driven/admin-editable (business
requirement: "Approval relationships must be configurable/data-driven, not
hardcoded") without a schema change if the shape of the org chart changes.

Which Group is a given approval's routed-to "Lead" is intentionally NOT a
column here -- it is derived from existing data (``User`` rows with
``role_id`` pointing at LEAD/MANAGER and ``group_id`` == that Group), so a
Group's lead can change via ordinary user management, and this table only
ever needs to encode "who manages whom".
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class GroupHierarchyEdge(Base):
    """A directed edge: ``parent_group`` manages/leads-over ``child_group``."""

    __tablename__ = "group_hierarchy_edges"
    __table_args__ = (
        UniqueConstraint("parent_group_id", "child_group_id", name="uq_group_hierarchy_edge"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    child_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    parent_group = relationship("Group", foreign_keys=[parent_group_id], back_populates="parent_edges")
    child_group = relationship("Group", foreign_keys=[child_group_id], back_populates="child_edges")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<GroupHierarchyEdge parent={0} child={1}>".format(self.parent_group_id, self.child_group_id)
