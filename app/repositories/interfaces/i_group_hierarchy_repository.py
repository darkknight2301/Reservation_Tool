"""Repository interface (Protocol) for the GroupHierarchyEdge aggregate."""
from typing import List, Optional, Protocol

from app.models.group_hierarchy_edge import GroupHierarchyEdge


class IGroupHierarchyRepository(Protocol):
    """Persistence contract for the data-driven, domain-scoped approval-hierarchy graph."""

    def get_parent_group_ids(self, group_id: int, scope: Optional[str] = None) -> List[int]:
        """
        Every group_id that is a direct parent (manages/leads-over) the
        given group. When ``scope`` is given, only edges tagged that scope
        or ``BOTH`` are considered; ``None`` considers every edge
        regardless of scope (used by admin listing, not by routing).
        """
        ...

    def get_child_group_ids(self, group_id: int, scope: Optional[str] = None) -> List[int]:
        """Every group_id that is a direct child of the given group, filtered by scope as above."""
        ...

    def list_all(self) -> List[GroupHierarchyEdge]:
        """Every edge in the hierarchy (admin/read use)."""
        ...

    def create_edge(self, parent_group_id: int, child_group_id: int, scope: str) -> GroupHierarchyEdge:
        ...

    def delete_edge(self, parent_group_id: int, child_group_id: int, scope: str) -> bool:
        ...
