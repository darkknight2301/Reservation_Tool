"""
Business-logic tests: call the service layer directly (real repositories,
one shared db_session/transaction) rather than going through HTTP, so these
focus purely on business RULES -- overlap validation, the Reservation/Swap
independence rule, and hierarchy-routed Swap approval -- independent of the
API/routing layer (already covered in test_backend.py).
"""
import pytest
from datetime import datetime, timedelta

from app.core.constants import ReservationStatus, RoleName, SetupStatus, SwapStatus
from app.core.exceptions import AuthorizationError, ReservationConflictError
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
from app.repositories.sqlalchemy.hardware_change_log_repository import HardwareChangeLogRepository
from app.repositories.sqlalchemy.reservation_repository import ReservationRepository
from app.repositories.sqlalchemy.role_repository import RoleRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.repositories.sqlalchemy.swap_repository import SwapRepository
from app.repositories.sqlalchemy.user_repository import UserRepository
from app.schemas.reservation import ReservationCreateRequest, ReservationFilter
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest
from app.services.approval_routing_service import ApprovalRoutingService
from app.services.audit_service import AuditService
from app.services.reservation_service import ReservationService
from app.services.role_lookup_service import RoleLookupService
from app.services.swap_service import SwapService


@pytest.fixture
def services(db_session):
    """Bundle of real service instances, all sharing one db_session/transaction."""
    audit_service = AuditService(AuditLogRepository(db_session))
    role_lookup_service = RoleLookupService(RoleRepository(db_session))
    setup_repository = SetupRepository(db_session)
    reservation_repository = ReservationRepository(db_session)
    swap_repository = SwapRepository(db_session)
    group_hierarchy_repository = GroupHierarchyRepository(db_session)
    hardware_change_log_repository = HardwareChangeLogRepository(db_session)
    user_repository = UserRepository(db_session)
    approval_routing_service = ApprovalRoutingService(group_hierarchy_repository, user_repository)

    reservation_service = ReservationService(
        reservation_repository, setup_repository, role_lookup_service, audit_service, None
    )
    swap_service = SwapService(
        swap_repository, reservation_repository, setup_repository, audit_service,
        hardware_change_log_repository, approval_routing_service,
    )

    class _Services:
        pass

    bundle = _Services()
    bundle.reservation_service = reservation_service
    bundle.swap_service = swap_service
    bundle.setup_repository = setup_repository
    bundle.reservation_repository = reservation_repository
    bundle.group_hierarchy_repository = group_hierarchy_repository
    return bundle


def _window():
    start = datetime.utcnow() + timedelta(hours=1)
    return start, start + timedelta(hours=2)


# ---------------------------------------------------------------------
# Reservation business rules
# ---------------------------------------------------------------------

def test_available_setup_can_be_reserved(services, developer_user, setup):
    start, end = _window()
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    assert reservation.status == ReservationStatus.ACTIVE
    assert reservation.user_id == developer_user.id

    refreshed_setup = services.setup_repository.get_by_id(setup.id)
    assert refreshed_setup.status == SetupStatus.RESERVED


def test_already_reserved_setup_cannot_be_reserved_again(services, developer_user, second_developer_user, setup):
    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    with pytest.raises(ReservationConflictError):
        services.reservation_service.create(
            ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end),
            second_developer_user,
        )


def test_reservation_always_belongs_to_acting_user(services, developer_user, second_developer_user, setup):
    """A reservation's user_id is always the acting user -- there is no way to reserve 'as' someone else."""
    start, end = _window()
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    assert reservation.user_id == developer_user.id
    assert reservation.user_id != second_developer_user.id


def test_two_users_cannot_both_hold_active_reservation_on_same_setup(
    services, developer_user, second_developer_user, setup
):
    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    with pytest.raises(ReservationConflictError):
        services.reservation_service.create(
            ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end),
            second_developer_user,
        )

    active = services.reservation_repository.list_all(
        ReservationFilter(setup_id=setup.id, status=ReservationStatus.ACTIVE)
    )
    assert len(active) == 1
    assert active[0].user_id == developer_user.id


def test_non_overlapping_windows_on_same_setup_both_allowed(services, developer_user, second_developer_user, setup):
    """Two reservations on the same setup are fine as long as their time windows don't overlap."""
    start_one = datetime.utcnow() + timedelta(hours=1)
    end_one = start_one + timedelta(hours=1)
    start_two = end_one + timedelta(hours=1)
    end_two = start_two + timedelta(hours=1)

    first = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start_one, reserved_until=end_one), developer_user
    )
    second = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start_two, reserved_until=end_two),
        second_developer_user,
    )
    assert first.status == ReservationStatus.ACTIVE
    assert second.status == ReservationStatus.ACTIVE


# ---------------------------------------------------------------------
# Unreserve business rules
# ---------------------------------------------------------------------

def test_own_reservation_can_be_unreserved(services, developer_user, setup):
    start, end = _window()
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    cancelled = services.reservation_service.cancel(reservation.id, developer_user)
    assert cancelled.status == ReservationStatus.CANCELLED
    assert services.setup_repository.get_by_id(setup.id).status == SetupStatus.AVAILABLE


def test_another_users_reservation_cannot_be_unreserved(services, developer_user, second_developer_user, setup):
    start, end = _window()
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup.id, reserved_from=start, reserved_until=end), developer_user
    )
    with pytest.raises(AuthorizationError):
        services.reservation_service.cancel(reservation.id, second_developer_user)


def test_unreserve_allowed_while_swap_pending(services, developer_user, make_setup, product):
    """
    Reservation and Swap are independent workflows (business rule 1):
    cancelling a reservation no longer waits on, or is blocked by, any
    pending Swap request against it -- see ARCHITECTURE_ASSESSMENT.md
    section 3.1 / IMPLEMENTATION_PROGRESS.md Phase 2.
    """
    start, end = _window()
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )

    services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id), developer_user
    )

    cancelled = services.reservation_service.cancel(reservation.id, developer_user)
    assert cancelled.status == ReservationStatus.CANCELLED


def test_swap_approval_succeeds_even_after_its_originating_reservation_was_cancelled(
    services, developer_user, make_user, make_setup, product
):
    """
    Phase 3 completes the independence established in Phase 2: a Swap now
    exchanges hardware values between two setups and never touches, or
    re-checks, any Reservation -- so approving a swap after the requester's
    original reservation was separately cancelled still succeeds (unlike
    the pre-Phase-3 design, which relocated the reservation and therefore
    had to re-verify it was still active).
    """
    start, end = _window()
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )
    reservation_b = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_b.id, reserved_from=start, reserved_until=end), developer_user
    )

    swap = services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id, column_names=["ssd"]),
        developer_user,
    )

    services.reservation_service.cancel(reservation_b.id, developer_user)

    approver = make_user(role_name=RoleName.LEAD)
    approved = services.swap_service.approve(swap.id, SwapDecisionRequest(), approver)
    assert approved.status == SwapStatus.COMPLETED


# ---------------------------------------------------------------------
# Hierarchy-routed Swap approval
# ---------------------------------------------------------------------

def test_swap_approval_routes_to_the_setups_group_lead(services, db_session, make_user, make_setup, product):
    """A Lead of the current setup's own group (no hierarchy edges needed) may approve."""
    from app.models.group import Group

    group = Group(name="Group-{0}".format(id(product)))
    db_session.add(group)
    db_session.flush()

    requester = make_user()
    group_lead = make_user(role_name=RoleName.LEAD, group_id=group.id)
    unrelated_lead = make_user(role_name=RoleName.LEAD)

    setup_a = make_setup(product_id=product.id, group_id=group.id)
    setup_b = make_setup(product_id=product.id)

    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), requester
    )
    swap = services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id, column_names=["ssd"]), requester
    )

    # A Lead with no relationship to setup_a's group is not among the
    # routed approvers and must be refused.
    with pytest.raises(AuthorizationError):
        services.swap_service.approve(swap.id, SwapDecisionRequest(), unrelated_lead)

    # The setup's own group's Lead IS a routed approver.
    approved = services.swap_service.approve(swap.id, SwapDecisionRequest(), group_lead)
    assert approved.status == SwapStatus.COMPLETED


def test_swap_approval_routes_to_an_ancestor_groups_lead(services, db_session, make_user, make_setup, product):
    """
    Reproduces the business-rule Swap routing example: J's approval routes
    to its own group's leads AND its ancestor groups' leads (the full
    ancestor chain), not just an immediate parent.
    """
    from app.models.group import Group
    from app.models.group_hierarchy_edge import GroupHierarchyEdge

    db = db_session
    child_group = Group(name="Child-{0}".format(id(product)))
    parent_group = Group(name="Parent-{0}".format(id(product)))
    grandparent_group = Group(name="Grandparent-{0}".format(id(product)))
    db.add_all([child_group, parent_group, grandparent_group])
    db.flush()
    db.add_all([
        GroupHierarchyEdge(parent_group_id=parent_group.id, child_group_id=child_group.id),
        GroupHierarchyEdge(parent_group_id=grandparent_group.id, child_group_id=parent_group.id),
    ])
    db.flush()

    requester = make_user()
    grandparent_lead = make_user(role_name=RoleName.LEAD, group_id=grandparent_group.id)

    setup_a = make_setup(product_id=product.id, group_id=child_group.id)
    setup_b = make_setup(product_id=product.id)

    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), requester
    )
    swap = services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id, column_names=["ssd"]), requester
    )

    # The grandparent group's Lead is two hops up the hierarchy -- still a
    # valid routed approver, per the full-ancestor-closure rule.
    approved = services.swap_service.approve(swap.id, SwapDecisionRequest(), grandparent_lead)
    assert approved.status == SwapStatus.COMPLETED


def test_swap_approval_falls_back_to_flat_permission_when_hierarchy_unconfigured(
    services, db_session, make_user, make_setup, product
):
    """
    No hierarchy edges and no Lead assigned to the setup's group at all:
    approval falls back to the pre-Phase-3 flat swap:approve permission
    (any Lead/Manager/Owner) rather than becoming permanently unreachable.
    """
    from app.models.group import Group

    group = Group(name="Orphan-{0}".format(id(product)))
    db_session.add(group)
    db_session.flush()

    requester = make_user()
    any_lead = make_user(role_name=RoleName.LEAD)  # not a member of `group` at all

    setup_a = make_setup(product_id=product.id, group_id=group.id)  # group has no Lead of its own
    setup_b = make_setup(product_id=product.id)

    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), requester
    )
    swap = services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id, column_names=["ssd"]), requester
    )

    approved = services.swap_service.approve(swap.id, SwapDecisionRequest(), any_lead)
    assert approved.status == SwapStatus.COMPLETED


def test_swap_approval_exchanges_values_and_logs_hardware_change_history(
    services, db_session, developer_user, make_user, make_setup, product
):
    """The core Swap operation: values are exchanged between the two setups, and a HardwareChangeLog row is written for each side."""
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    setup_a.ssd = "Original-A"
    setup_b.ssd = "Original-B"
    db_session.add_all([setup_a, setup_b])
    db_session.flush()

    start, end = _window()
    services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )
    swap = services.swap_service.create(
        SwapCreateRequest(current_setup_id=setup_a.id, requested_setup_id=setup_b.id, column_names=["ssd"]),
        developer_user,
    )

    approver = make_user(role_name=RoleName.LEAD)
    services.swap_service.approve(swap.id, SwapDecisionRequest(), approver)

    refreshed_a = services.setup_repository.get_by_id(setup_a.id)
    refreshed_b = services.setup_repository.get_by_id(setup_b.id)
    assert refreshed_a.ssd == "Original-B"
    assert refreshed_b.ssd == "Original-A"

    # Reservation on setup_a must be completely unaffected -- no relocation.
    active_on_a = services.reservation_repository.get_active_by_setup_id(setup_a.id)
    assert active_on_a is not None
    assert active_on_a.user_id == developer_user.id

    from app.models.hardware_change_log import HardwareChangeLog

    logs = db_session.query(HardwareChangeLog).filter(HardwareChangeLog.source_request_id == swap.id).all()
    assert {(log.setup_id, log.field_name, log.old_value, log.new_value) for log in logs} == {
        (setup_a.id, "ssd", "Original-A", "Original-B"),
        (setup_b.id, "ssd", "Original-B", "Original-A"),
    }


# ---------------------------------------------------------------------
# Borrow approval routing (ApprovalRoutingService.resolve_borrow_approvers)
# ---------------------------------------------------------------------
#
# These test the routing ALGORITHM directly against ApprovalRoutingService,
# independent of any BorrowService (which does not exist yet -- see
# IMPLEMENTATION_PROGRESS.md, still scheduled). Business rule 8 ("hierarchy
# affects routing, not general access") and "Keep Swap and Borrow approval
# logic independent" are both exercised here.

def test_borrow_routing_matches_the_business_rule_example(services, db_session, make_user):
    """
    Reproduces the business-rule Borrow example exactly:
    Group 2: a -> d,e ; b -> d,f,g ; c -> h,i,b
    "E requests Borrow from d" -> approval goes to b,d,f,g.
    """
    from app.models.group import Group
    from app.models.group_hierarchy_edge import GroupHierarchyEdge
    from app.core.constants import ApprovalHierarchyScope

    db = db_session
    groups = {name: Group(name="{0}-{1}".format(name, id(services))) for name in "abcdefghi"}
    db.add_all(groups.values())
    db.flush()

    edges = [
        ("a", "d"), ("a", "e"),
        ("b", "d"), ("b", "f"), ("b", "g"),
        ("c", "h"), ("c", "i"), ("c", "b"),
    ]
    db.add_all([
        GroupHierarchyEdge(
            parent_group_id=groups[p].id, child_group_id=groups[c].id, scope=ApprovalHierarchyScope.BORROW
        )
        for p, c in edges
    ])
    db.flush()

    # A Lead/Manager in each of b, d, f, g so the expected answer is non-empty.
    lead_b = make_user(role_name=RoleName.LEAD, group_id=groups["b"].id)
    lead_d = make_user(role_name=RoleName.LEAD, group_id=groups["d"].id)
    lead_f = make_user(role_name=RoleName.LEAD, group_id=groups["f"].id)
    lead_g = make_user(role_name=RoleName.LEAD, group_id=groups["g"].id)
    # A decoy Lead in `a` and `e` -- must NOT be included in the result,
    # even though "a -> d,e" technically makes `a` a parent of `d` too.
    make_user(role_name=RoleName.LEAD, group_id=groups["a"].id)
    make_user(role_name=RoleName.LEAD, group_id=groups["e"].id)

    from app.services.approval_routing_service import ApprovalRoutingService
    from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
    from app.repositories.sqlalchemy.user_repository import UserRepository

    routing = ApprovalRoutingService(GroupHierarchyRepository(db), UserRepository(db))
    approvers = routing.resolve_borrow_approvers(groups["d"].id)

    assert {u.id for u in approvers} == {lead_b.id, lead_d.id, lead_f.id, lead_g.id}


def test_swap_and_borrow_hierarchy_edges_stay_independent_when_sharing_a_group(services, db_session, make_user):
    """
    The same Group can be a child under a SWAP-scoped edge from one parent
    and a BORROW-scoped edge from a different parent (exactly the business
    rule examples' shared Group D). Swap routing must only ever see the
    SWAP edge; Borrow routing must only ever see the BORROW edge.
    """
    from app.models.group import Group
    from app.models.group_hierarchy_edge import GroupHierarchyEdge
    from app.core.constants import ApprovalHierarchyScope
    from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
    from app.repositories.sqlalchemy.user_repository import UserRepository
    from app.services.approval_routing_service import ApprovalRoutingService

    db = db_session
    shared_child = Group(name="Shared-{0}".format(id(services)))
    swap_parent = Group(name="SwapParent-{0}".format(id(services)))
    borrow_parent = Group(name="BorrowParent-{0}".format(id(services)))
    borrow_sibling = Group(name="BorrowSibling-{0}".format(id(services)))
    db.add_all([shared_child, swap_parent, borrow_parent, borrow_sibling])
    db.flush()

    db.add_all([
        GroupHierarchyEdge(parent_group_id=swap_parent.id, child_group_id=shared_child.id, scope=ApprovalHierarchyScope.SWAP),
        GroupHierarchyEdge(parent_group_id=borrow_parent.id, child_group_id=shared_child.id, scope=ApprovalHierarchyScope.BORROW),
        GroupHierarchyEdge(parent_group_id=borrow_parent.id, child_group_id=borrow_sibling.id, scope=ApprovalHierarchyScope.BORROW),
    ])
    db.flush()

    swap_parent_lead = make_user(role_name=RoleName.LEAD, group_id=swap_parent.id)
    borrow_parent_lead = make_user(role_name=RoleName.LEAD, group_id=borrow_parent.id)

    routing = ApprovalRoutingService(GroupHierarchyRepository(db), UserRepository(db))

    swap_ancestors = routing.ancestor_group_ids(shared_child.id, ApprovalHierarchyScope.SWAP)
    assert swap_parent.id in swap_ancestors
    assert borrow_parent.id not in swap_ancestors  # BORROW-scoped edge must be invisible to SWAP routing

    borrow_approvers = routing.resolve_borrow_approvers(shared_child.id)
    assert {u.id for u in borrow_approvers} == {borrow_parent_lead.id}
    assert swap_parent_lead.id not in {u.id for u in borrow_approvers}  # SWAP-scoped edge must be invisible to BORROW routing


def test_borrow_routing_falls_back_to_the_selected_groups_own_lead_when_it_has_no_borrow_parent(services, db_session, make_user):
    """A root group (no BORROW-scoped parent) still resolves to its own Lead, not an empty/broken result."""
    from app.models.group import Group
    from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
    from app.repositories.sqlalchemy.user_repository import UserRepository
    from app.services.approval_routing_service import ApprovalRoutingService

    db = db_session
    root_group = Group(name="Root-{0}".format(id(services)))
    db.add(root_group)
    db.flush()
    lead = make_user(role_name=RoleName.LEAD, group_id=root_group.id)

    routing = ApprovalRoutingService(GroupHierarchyRepository(db), UserRepository(db))
    approvers = routing.resolve_borrow_approvers(root_group.id)
    assert {u.id for u in approvers} == {lead.id}


# ---------------------------------------------------------------------
# Approval states include EXPIRED (business rule: "pending / approved /
# rejected / cancelled / expired where applicable")
# ---------------------------------------------------------------------

def test_swap_and_borrow_status_enums_support_expired():
    from app.core.constants import BorrowStatus

    assert SwapStatus.EXPIRED == "EXPIRED"
    assert SwapStatus.EXPIRED in SwapStatus.ALL
    assert BorrowStatus.EXPIRED == "EXPIRED"
    assert BorrowStatus.EXPIRED in BorrowStatus.ALL
