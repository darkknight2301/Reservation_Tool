"""
Group ORM model.

A Group represents an organizational team (e.g. "Networking Lab Team") that
users belong to and that setups can be assigned to for ownership/maintenance
purposes. Groups are independent of Products: a Product classifies *what*
a setup is (a product line), a Group classifies *who* maintains it.
"""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Group(Base):
    """A team/organizational unit that owns users and setups."""

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="group", foreign_keys="User.group_id")
    members = relationship("User", secondary="user_groups", back_populates="groups")
    setups = relationship("Setup", back_populates="group")

    # Data-driven approval-hierarchy edges (see app.models.group_hierarchy_edge).
    # "parent_edges": edges where this Group is the PARENT (i.e. the groups
    # this Group manages/leads-over). "child_edges": edges where this Group
    # is the CHILD (i.e. the groups that manage/lead this Group -- a Group
    # can have more than one, since the hierarchy is a DAG, not a tree).
    parent_edges = relationship(
        "GroupHierarchyEdge", foreign_keys="GroupHierarchyEdge.parent_group_id", back_populates="parent_group"
    )
    child_edges = relationship(
        "GroupHierarchyEdge", foreign_keys="GroupHierarchyEdge.child_group_id", back_populates="child_group"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Group id={0} name={1}>".format(self.id, self.name)
