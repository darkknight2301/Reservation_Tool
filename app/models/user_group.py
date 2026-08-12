"""
Many-to-many association between User and Group.

A User's existing ``group_id`` column (see ``app.models.user``) remains
their single *primary* group, used as-is by existing record-level RBAC
(e.g. "a LEAD may only approve users in their own group") and by
notification lookups. This table is additive: it lets a user belong to any
number of *additional* groups (multi-group membership), without changing
the meaning or behavior of ``group_id`` for existing code.
"""
from sqlalchemy import Column, ForeignKey, Integer, Table

from app.db.base import Base

user_groups = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
)
