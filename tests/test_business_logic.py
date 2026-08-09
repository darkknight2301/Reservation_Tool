"""
Business-logic tests: call the service layer directly (real repositories,
one shared db_session/transaction) rather than going through HTTP, so these
focus purely on business RULES -- overlap validation, swap-mapping
node-uniqueness/availability validation, and the unreserve/pending-swap
restriction -- independent of the API/routing layer (already covered in
test_backend.py).
"""
import pytest
from pydantic import ValidationError
from datetime import datetime, timedelta

from app.core.constants import ReservationStatus, SetupStatus, SwapStatus
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    ReservationConflictError,
    SwapMappingValidationError,
)
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.reservation_repository import ReservationRepository
from app.repositories.sqlalchemy.role_repository import RoleRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.repositories.sqlalchemy.swap_repository import SwapRepository
from app.schemas.reservation import ReservationCreateRequest, ReservationFilter
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest, SwapMappingCreateRequest, SwapMappingEntry
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

    reservation_service = ReservationService(
        reservation_repository, setup_repository, role_lookup_service, audit_service, swap_repository, None
    )
    swap_service = SwapService(swap_repository, reservation_repository, setup_repository, audit_service)

    class _Services:
        pass

    bundle = _Services()
    bundle.reservation_service = reservation_service
    bundle.swap_service = swap_service
    bundle.setup_repository = setup_repository
    bundle.reservation_repository = reservation_repository
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


def test_unreserve_blocked_while_swap_pending(services, developer_user, make_setup, product):
    start, end = _window()
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )

    services.swap_service.create(
        SwapCreateRequest(reservation_id=reservation.id, requested_setup_id=setup_b.id), developer_user
    )

    with pytest.raises(ConflictError):
        services.reservation_service.cancel(reservation.id, developer_user)


def test_unreserve_allowed_after_swap_restored_by_rejection(services, developer_user, make_user, make_setup, product):
    start, end = _window()
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )

    swap = services.swap_service.create(
        SwapCreateRequest(reservation_id=reservation.id, requested_setup_id=setup_b.id), developer_user
    )

    approver = make_user()
    services.swap_service.reject(swap.id, SwapDecisionRequest(), approver)

    # The swap is now REJECTED ("restored"), so unreserve must succeed.
    cancelled = services.reservation_service.cancel(reservation.id, developer_user)
    assert cancelled.status == ReservationStatus.CANCELLED


def test_unreserve_allowed_after_swap_restored_by_cancel(services, developer_user, make_setup, product):
    start, end = _window()
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    reservation = services.reservation_service.create(
        ReservationCreateRequest(setup_id=setup_a.id, reserved_from=start, reserved_until=end), developer_user
    )

    swap = services.swap_service.create(
        SwapCreateRequest(reservation_id=reservation.id, requested_setup_id=setup_b.id), developer_user
    )
    services.swap_service.cancel(swap.id, developer_user)

    cancelled = services.reservation_service.cancel(reservation.id, developer_user)
    assert cancelled.status == ReservationStatus.CANCELLED


# ---------------------------------------------------------------------
# Swap mapping validation matrix
# ---------------------------------------------------------------------

@pytest.fixture
def five_reservations(services, make_user, make_setup, product):
    """
    Five distinct users, each with an ACTIVE reservation on their own setup
    (A..E), plus one extra spare AVAILABLE setup for "target outside the
    cycle" scenarios. Returns a dict letter -> {"reservation": ..., "setup": ...}.
    """
    start, end = _window()
    letters = ["A", "B", "C", "D", "E"]
    result = {}
    for letter in letters:
        user = make_user()
        setup_obj = make_setup(product_id=product.id)
        reservation = services.reservation_service.create(
            ReservationCreateRequest(setup_id=setup_obj.id, reserved_from=start, reserved_until=end), user
        )
        result[letter] = {"user": user, "setup": setup_obj, "reservation": reservation}
    result["SPARE"] = {"setup": make_setup(product_id=product.id)}
    return result


def _mapping(*pairs):
    return [SwapMappingEntry(reservation_id=r_id, target_setup_id=s_id) for r_id, s_id in pairs]


def test_swap_mapping_valid_two_cycle(services, five_reservations, owner_user):
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["B"]["setup"].id),
        (nodes["B"]["reservation"].id, nodes["A"]["setup"].id),
    )
    created = services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)
    assert len(created) == 2
    assert all(swap.status == SwapStatus.PENDING for swap in created)

    batch_id = created[0].batch_id
    approved = services.swap_service.approve_mapping(batch_id, owner_user)
    assert all(swap.status == SwapStatus.COMPLETED for swap in approved)

    setup_a_after = services.setup_repository.get_by_id(nodes["A"]["setup"].id)
    setup_b_after = services.setup_repository.get_by_id(nodes["B"]["setup"].id)
    assert setup_a_after.status == SetupStatus.RESERVED
    assert setup_b_after.status == SetupStatus.RESERVED


def test_swap_mapping_valid_two_independent_cycles(services, five_reservations, owner_user):
    """A->B, C->D, D->E, E->C, B->A: a 2-cycle (A,B) plus a 3-cycle (C,D,E)."""
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["B"]["setup"].id),
        (nodes["C"]["reservation"].id, nodes["D"]["setup"].id),
        (nodes["D"]["reservation"].id, nodes["E"]["setup"].id),
        (nodes["E"]["reservation"].id, nodes["C"]["setup"].id),
        (nodes["B"]["reservation"].id, nodes["A"]["setup"].id),
    )
    created = services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)
    assert len(created) == 5

    approved = services.swap_service.approve_mapping(created[0].batch_id, owner_user)
    assert all(swap.status == SwapStatus.COMPLETED for swap in approved)

    for letter, target_letter in [("A", "B"), ("B", "A"), ("C", "D"), ("D", "E"), ("E", "C")]:
        setup_after = services.setup_repository.get_by_id(nodes[target_letter]["setup"].id)
        assert setup_after.status == SetupStatus.RESERVED


def test_swap_mapping_invalid_self_target(services, five_reservations, owner_user):
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["A"]["setup"].id),  # A -> A
        (nodes["C"]["reservation"].id, nodes["SPARE"]["setup"].id),
    )
    with pytest.raises(SwapMappingValidationError):
        services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)


def test_swap_mapping_invalid_duplicate_source(services, five_reservations, owner_user):
    """A -> B, A -> C: the same reservation (A) used as a source twice."""
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["B"]["setup"].id),
        (nodes["A"]["reservation"].id, nodes["C"]["setup"].id),
    )
    with pytest.raises(SwapMappingValidationError):
        services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)


def test_swap_mapping_invalid_duplicate_destination(services, five_reservations, owner_user):
    """A -> B, C -> B: two different sources targeting the same destination (B)."""
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["B"]["setup"].id),
        (nodes["C"]["reservation"].id, nodes["B"]["setup"].id),
    )
    with pytest.raises(SwapMappingValidationError):
        services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)


def test_swap_mapping_missing_mapping_rejected_by_schema():
    """A single-entry mapping ('missing' its partner) fails schema validation (min 2 entries)."""
    with pytest.raises(ValidationError):
        SwapMappingCreateRequest(mappings=[SwapMappingEntry(reservation_id=1, target_setup_id=2)])


def test_swap_mapping_incomplete_mapping_target_not_available(services, five_reservations, owner_user):
    """
    A -> B where B is reserved by its own occupant and NOT included in this
    mapping (an "incomplete" attempt at what should have been a full cycle):
    B is neither a source in this batch nor AVAILABLE, so the whole mapping
    must be rejected.
    """
    nodes = five_reservations
    mapping = _mapping(
        (nodes["A"]["reservation"].id, nodes["B"]["setup"].id),  # B is active-reserved by user B, not in this batch
        (nodes["C"]["reservation"].id, nodes["SPARE"]["setup"].id),
    )
    with pytest.raises(SwapMappingValidationError):
        services.swap_service.create_mapping(SwapMappingCreateRequest(mappings=mapping), owner_user)
