"""
Approval routing service.

Resolves *who* may approve a Swap or Borrow request, by walking the
data-driven ``group_hierarchy_edges`` graph
(``app.models.group_hierarchy_edge.GroupHierarchyEdge``) rather than any
hardcoded org chart -- see ARCHITECTURE_ASSESSMENT.md sections 4 and 10,
and the "Phase 1 Assumptions Adopted" section for the routing-rule and
fallback decisions this implements.

Routing rule (Swap, ``resolve_swap_approvers``): the full ancestor closure
of the requester's setup's owning Group -- i.e. every Lead/Manager of that
Group AND every Lead/Manager of any group that (directly or transitively)
manages it, considering only edges tagged ``SWAP`` or ``BOTH``. Matches the
Swap example in the business rules: ``A -> D,E -> J,K,L,M,N,O`` means J's
approval routes to D, E, *and* A.

Routing rule (Borrow, ``resolve_borrow_approvers``): deliberately
different, and considers only edges tagged ``BORROW`` or ``BOTH``. The
requesting Lead selects a target/source Lead's Group; approval routes to
that Group's own Lead/Manager, its direct parent's Lead/Manager, and every
sibling Group under that same parent. Matches the Borrow example: Group 2's
``b -> d,f,g`` means selecting Lead ``d`` for a Borrow routes to
``b, d, f, g``.

Why scope matters: the business-rule examples reuse Group D as a child of
BOTH A (in the Swap example) and B (in the Borrow example). Without
per-edge scoping, a graph walk for one domain would incorrectly pick up an
edge only ever meant for the other -- e.g. Borrow routing for D would
wrongly include A's branch too. Tagging each edge ``SWAP``, ``BORROW``, or
``BOTH`` (``ApprovalHierarchyScope``) keeps the two domains' approval logic
independent even though both read the same underlying table, exactly as
the business rules require ("Keep Swap and Borrow approval logic
independent").

Fallback (when no hierarchy edges are configured for a group yet, and that
group has no Lead/Manager of its own either): an empty approver list is
returned, and the caller falls back to the pre-Phase-3 flat ``swap:approve``
(or, for Borrow, ``borrow:approve``) permission check (any Lead/Manager/
Owner) so an approval can never become permanently unreachable just
because an admin hasn't populated the hierarchy yet.

Approval semantics: ANY ONE of the resolved approvers is sufficient (OR,
not AND) -- see ``SwapService.approve()`` and (once implemented) the Borrow
approval flow.
"""
from typing import List, Optional

from app.core.constants import ApprovalHierarchyScope, RoleName
from app.models.user import User
from app.repositories.interfaces.i_group_hierarchy_repository import IGroupHierarchyRepository
from app.repositories.interfaces.i_user_repository import IUserRepository

# Roles that can act as an approving "Lead" for hierarchy-routed approval.
# OWNER is deliberately excluded here -- Owner's ability to approve anything
# comes from the flat swap:approve/borrow:approve permission (business rule
# 8: hierarchy affects routing, not general access), not from being
# "routed to", so it is handled as a separate universal override by the
# caller rather than being folded into this set.
_APPROVER_ROLE_NAMES = (RoleName.LEAD, RoleName.MANAGER)


class ApprovalRoutingService:
    """Resolves the set of users who may approve a Swap or Borrow request against a given Group, via the hierarchy graph."""

    def __init__(
        self,
        group_hierarchy_repository: IGroupHierarchyRepository,
        user_repository: IUserRepository,
    ) -> None:
        self._group_hierarchy_repository = group_hierarchy_repository
        self._user_repository = user_repository

    def ancestor_group_ids(self, group_id: int, scope: str) -> List[int]:
        """
        Every group_id reachable by walking parent edges (of the given
        scope, or tagged BOTH) upward from ``group_id``, including
        ``group_id`` itself. Guards against cycles defensively with a
        visited-set (the DAG is expected to be acyclic -- enforced by the
        service layer at edge-creation time, see
        ``GroupHierarchyRepository.create_edge`` -- but a traversal must
        never infinite-loop even if that invariant is ever violated).
        """
        visited = {group_id}
        frontier = [group_id]
        while frontier:
            next_frontier: List[int] = []
            for current_id in frontier:
                for parent_id in self._group_hierarchy_repository.get_parent_group_ids(current_id, scope):
                    if parent_id not in visited:
                        visited.add(parent_id)
                        next_frontier.append(parent_id)
            frontier = next_frontier
        return list(visited)

    def resolve_swap_approvers(self, group_id: Optional[int]) -> List[User]:
        """
        Every Lead/Manager of ``group_id`` or any of its ancestor groups,
        considering only SWAP/BOTH-scoped edges. Returns an empty list if
        ``group_id`` is None or no such user exists -- the caller falls
        back to the flat ``swap:approve`` permission in that case.
        """
        if group_id is None:
            return []
        ancestor_ids = self.ancestor_group_ids(group_id, ApprovalHierarchyScope.SWAP)
        return self._user_repository.list_active_by_group_ids_and_roles(ancestor_ids, list(_APPROVER_ROLE_NAMES))

    # Backward-compatible alias -- SwapService (Phase 3) calls this name.
    resolve_approvers_for_group = resolve_swap_approvers

    def resolve_borrow_approvers(self, selected_group_id: Optional[int]) -> List[User]:
        """
        Routing rule for Borrow (deliberately different from Swap's full
        ancestor closure -- see the business-rule example): the requesting
        Lead selects a target/source Lead's Group; approval routes to that
        Group's own Lead/Manager, its DIRECT parent Group's Lead/Manager,
        and every OTHER Group sharing that same parent (its "siblings"),
        considering only BORROW/BOTH-scoped edges.

        Reproduces the business-rule example exactly: Group 2 has
        ``b -> d,f,g`` (b is the parent of d, f, and g, tagged BORROW).
        Selecting Lead ``d`` for a Borrow routes approval to ``b, d, f,
        g`` -- the parent plus the full sibling set, including ``d``
        itself -- even though ``d`` is ALSO a child of ``a`` in the Swap
        example, because that edge is tagged SWAP and is therefore
        invisible to this BORROW-scoped walk. If the selected group has no
        BORROW-scoped parent at all (a root group in this domain), routing
        falls back to just that group's own Lead/Manager. Returns an empty
        list if ``selected_group_id`` is None or no qualifying user exists
        at all anywhere in that set -- the caller falls back to the flat
        ``borrow:approve`` permission in that case.
        """
        if selected_group_id is None:
            return []

        parent_ids = self._group_hierarchy_repository.get_parent_group_ids(
            selected_group_id, ApprovalHierarchyScope.BORROW
        )
        target_group_ids = {selected_group_id}
        target_group_ids.update(parent_ids)
        for parent_id in parent_ids:
            target_group_ids.update(
                self._group_hierarchy_repository.get_child_group_ids(parent_id, ApprovalHierarchyScope.BORROW)
            )

        return self._user_repository.list_active_by_group_ids_and_roles(
            list(target_group_ids), list(_APPROVER_ROLE_NAMES)
        )
