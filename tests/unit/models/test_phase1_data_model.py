"""
Phase 1 (Data Model) validation tests.

These exercise the new ORM models/columns introduced for Borrow, the
data-driven approval hierarchy, and the hardware Original/Baseline +
change-ledger split -- at the persistence layer only (no service logic
exists yet; that is Phase 2-4). They confirm:

  * every new table round-trips through the real declarative Base
    (``Base.metadata.create_all`` picks them up because they are imported
    in ``app/models/__init__.py``);
  * existing tables/rows are unaffected by the additive columns (business
    rule: "Preserve existing data through migration. Do not delete original
    information.");
  * the DAG shape required by the Borrow approval example (a Group with
    more than one parent) is representable;
  * the CHECK-constraint-equivalent invariants hold at the ORM/DB level
    (self-loop edges, unknown hardware-change source).
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.constants import BorrowStatus, HardwareChangeSource
from app.models.borrow_request import BorrowRequest
from app.models.group_hierarchy_edge import GroupHierarchyEdge
from app.models.hardware_change_log import HardwareChangeLog
from app.models.setup_access_grant import SetupAccessGrant
from app.models.setup_hardware_baseline import SetupHardwareBaseline
from app.models.swap_request import SwapRequest


# ---------------------------------------------------------------------
# Hardware Original/Baseline snapshot + change ledger
# ---------------------------------------------------------------------

def test_setup_hardware_baseline_can_be_captured_and_is_independent_of_current_value(db_session, setup):
    """Baseline is a separate row; mutating the live Setup does not touch it."""
    baseline = SetupHardwareBaseline(setup_id=setup.id, ssd="Baseline-SSD", hdd="Baseline-HDD")
    db_session.add(baseline)
    db_session.commit()

    # Simulate a swap changing the CURRENT/EFFECTIVE value on the Setup row.
    setup.ssd = "New-SSD-After-Swap"
    db_session.add(setup)
    db_session.commit()
    db_session.refresh(setup)

    stored_baseline = db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one()
    assert stored_baseline.ssd == "Baseline-SSD", "Baseline must not change when the effective value changes."
    assert setup.ssd == "New-SSD-After-Swap"


def test_setup_hardware_baseline_unique_per_setup(db_session, setup):
    """Only one baseline row is legal per Setup (uq_setup_hardware_baseline_setup_id)."""
    db_session.add(SetupHardwareBaseline(setup_id=setup.id, ssd="A"))
    db_session.commit()

    db_session.add(SetupHardwareBaseline(setup_id=setup.id, ssd="B"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_hardware_change_log_preserves_full_history_across_multiple_changes(db_session, setup, developer_user):
    """
    A field changed twice must leave BOTH change rows queryable (the exact
    gap in the pre-Phase-1 design: a single previous_value slot only ever
    remembers the most recent prior value).
    """
    db_session.add_all([
        HardwareChangeLog(
            setup_id=setup.id, field_name="ssd", old_value="Original-SSD", new_value="Swap1-SSD",
            source=HardwareChangeSource.SWAP, source_request_id=101, changed_by_id=developer_user.id,
        ),
        HardwareChangeLog(
            setup_id=setup.id, field_name="ssd", old_value="Swap1-SSD", new_value="Swap2-SSD",
            source=HardwareChangeSource.SWAP, source_request_id=102, changed_by_id=developer_user.id,
        ),
    ])
    db_session.commit()

    history = (
        db_session.query(HardwareChangeLog)
        .filter_by(setup_id=setup.id, field_name="ssd")
        .order_by(HardwareChangeLog.id)
        .all()
    )
    assert [row.old_value for row in history] == ["Original-SSD", "Swap1-SSD"]
    assert [row.new_value for row in history] == ["Swap1-SSD", "Swap2-SSD"]


def test_hardware_change_log_rejects_unknown_source(db_session, setup):
    db_session.add(HardwareChangeLog(setup_id=setup.id, field_name="ssd", source="BOGUS"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------
# Data-driven approval hierarchy (DAG, not a strict tree)
# ---------------------------------------------------------------------

def test_group_hierarchy_supports_a_child_with_multiple_parents(db_session, group):
    """
    Reproduces the Borrow routing example structure: 'A -> D,E; B -> D,F,G'
    -- group D has two parents (A and B). A single parent_group_id column
    could not express this; the edge table must.
    """
    group_a = group
    n = id(group_a)  # ensure unique names without importing the private counter helper
    from app.models.group import Group

    group_b = Group(name="B-{0}".format(n))
    group_d = Group(name="D-{0}".format(n))
    db_session.add_all([group_b, group_d])
    db_session.commit()

    db_session.add_all([
        GroupHierarchyEdge(parent_group_id=group_a.id, child_group_id=group_d.id),
        GroupHierarchyEdge(parent_group_id=group_b.id, child_group_id=group_d.id),
    ])
    db_session.commit()

    parents_of_d = (
        db_session.query(GroupHierarchyEdge.parent_group_id)
        .filter(GroupHierarchyEdge.child_group_id == group_d.id)
        .all()
    )
    assert {row[0] for row in parents_of_d} == {group_a.id, group_b.id}


def test_group_hierarchy_rejects_self_loop(db_session, group):
    db_session.add(GroupHierarchyEdge(parent_group_id=group.id, child_group_id=group.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_group_hierarchy_rejects_duplicate_edge(db_session, group):
    from app.models.group import Group

    other = Group(name="Other-{0}".format(id(group)))
    db_session.add(other)
    db_session.commit()

    db_session.add(GroupHierarchyEdge(parent_group_id=group.id, child_group_id=other.id))
    db_session.commit()

    db_session.add(GroupHierarchyEdge(parent_group_id=group.id, child_group_id=other.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------
# Borrow aggregate + derived access grant
# ---------------------------------------------------------------------

def test_borrow_request_round_trips_reason_start_end_and_announcement(db_session, setup, group, developer_user):
    """Business rule 2: Borrow must support reason, start/end time, and announcement channels."""
    from app.models.group import Group

    target_group = Group(name="Target-{0}".format(id(setup)))
    db_session.add(target_group)
    db_session.commit()

    start = datetime.utcnow()
    end = start + timedelta(days=3)
    borrow = BorrowRequest(
        requester_id=developer_user.id,
        source_group_id=group.id,
        target_group_id=target_group.id,
        setup_id=setup.id,
        hardware_field_name=None,  # whole-setup borrow
        reason="Need extra capacity for a release burn-in",
        start_time=start,
        end_time=end,
        announcement_channels="WALL,MAIL_LEADS",
        status=BorrowStatus.PENDING,
        routed_approver_emails="lead1@example.com,lead2@example.com",
    )
    db_session.add(borrow)
    db_session.commit()
    db_session.refresh(borrow)

    assert borrow.status == BorrowStatus.PENDING
    assert borrow.reason.startswith("Need extra capacity")
    assert borrow.start_time == start
    assert borrow.end_time == end
    assert borrow.announcement_channels == "WALL,MAIL_LEADS"
    assert borrow.hardware_field_name is None  # supports whole-setup borrowing


def test_borrow_request_supports_specific_hardware_field_borrowing(db_session, setup, group, developer_user):
    """Business rule: Borrow must be able to represent a specific-hardware borrow, not only a whole setup."""
    from app.models.group import Group

    target_group = Group(name="Target2-{0}".format(id(setup)))
    db_session.add(target_group)
    db_session.commit()

    borrow = BorrowRequest(
        requester_id=developer_user.id,
        source_group_id=group.id,
        target_group_id=target_group.id,
        setup_id=setup.id,
        hardware_field_name="ssd",
        status=BorrowStatus.PENDING,
    )
    db_session.add(borrow)
    db_session.commit()
    db_session.refresh(borrow)

    assert borrow.hardware_field_name == "ssd"


def test_setup_access_grant_derives_effective_access_without_overwriting_group_id(
    db_session, make_setup, group, developer_user
):
    """
    An approved Borrow creates a grant; Setup.group_id (the ORIGINAL owning
    group) must remain untouched -- effective access is meant to be derived
    by reading the active grant, not by mutating ownership.
    """
    from app.models.group import Group

    setup = make_setup(group_id=group.id)
    original_group_id = setup.group_id
    assert original_group_id == group.id
    borrower_group = Group(name="Borrower-{0}".format(id(setup)))
    db_session.add(borrower_group)
    db_session.commit()

    borrow = BorrowRequest(
        requester_id=developer_user.id,
        source_group_id=group.id,
        target_group_id=borrower_group.id,
        setup_id=setup.id,
        status=BorrowStatus.COMPLETED,
    )
    db_session.add(borrow)
    db_session.commit()
    db_session.refresh(borrow)

    grant = SetupAccessGrant(
        setup_id=setup.id,
        borrow_request_id=borrow.id,
        source_group_id=group.id,
        granted_to_group_id=borrower_group.id,
        is_active=True,
    )
    db_session.add(grant)
    db_session.commit()

    db_session.refresh(setup)
    assert setup.group_id == original_group_id, "Borrow must never overwrite the Setup's original owning group."

    active_grant = (
        db_session.query(SetupAccessGrant).filter_by(setup_id=setup.id, is_active=True).one()
    )
    assert active_grant.granted_to_group_id == borrower_group.id

    # Return: close the grant, never delete it (history preserved).
    active_grant.is_active = False
    db_session.add(active_grant)
    db_session.commit()

    still_present = db_session.query(SetupAccessGrant).filter_by(id=active_grant.id).one()
    assert still_present.is_active is False


def test_setup_access_grant_unique_per_borrow_request(db_session, setup, group, developer_user):
    from app.models.group import Group

    borrower_group = Group(name="Borrower2-{0}".format(id(setup)))
    db_session.add(borrower_group)
    db_session.commit()

    borrow = BorrowRequest(
        requester_id=developer_user.id, source_group_id=group.id, target_group_id=borrower_group.id,
        setup_id=setup.id, status=BorrowStatus.COMPLETED,
    )
    db_session.add(borrow)
    db_session.commit()
    db_session.refresh(borrow)

    db_session.add(SetupAccessGrant(
        setup_id=setup.id, borrow_request_id=borrow.id,
        source_group_id=group.id, granted_to_group_id=borrower_group.id,
    ))
    db_session.commit()

    db_session.add(SetupAccessGrant(
        setup_id=setup.id, borrow_request_id=borrow.id,
        source_group_id=group.id, granted_to_group_id=borrower_group.id,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------
# Swap redesign columns (additive; legacy rows must still read back intact)
# ---------------------------------------------------------------------

def test_new_style_swap_request_populates_setup_id_without_relocation_columns(
    db_session, setup, developer_user
):
    """
    New-style Swap rows (Phase 3 will write these) target a single Setup
    directly and never populate the legacy relocation-shaped columns.
    """
    swap = SwapRequest(
        requester_id=developer_user.id,
        setup_id=setup.id,
        reservation_id=None,
        current_setup_id=None,
        requested_setup_id=None,
        column_name="ssd,hdd",
        reason="Upgrade before a demo",
        start_time=None,
        end_time=None,
        announcement_channels="WALL",
        routed_approver_emails="lead@example.com",
    )
    db_session.add(swap)
    db_session.commit()
    db_session.refresh(swap)

    assert swap.setup_id == setup.id
    assert swap.reservation_id is None
    assert swap.current_setup_id is None
    assert swap.requested_setup_id is None
    assert swap.column_names == ["ssd", "hdd"]


def test_legacy_style_swap_request_still_valid_after_migration(db_session, make_setup, developer_user):
    """
    A row shaped exactly like pre-Phase-1 code would have written (relocation
    columns populated, setup_id NULL) must still insert cleanly -- existing
    history is never rewritten or invalidated by the additive migration.
    """
    from app.core.constants import ReservationStatus
    from app.models.reservation import Reservation

    current = make_setup()
    requested = make_setup()
    start = datetime.utcnow()
    reservation = Reservation(
        setup_id=current.id, user_id=developer_user.id,
        reserved_from=start, reserved_until=start + timedelta(hours=2),
        status=ReservationStatus.ACTIVE,
    )
    db_session.add(reservation)
    db_session.commit()
    db_session.refresh(reservation)

    legacy_swap = SwapRequest(
        reservation_id=reservation.id,
        requester_id=developer_user.id,
        current_setup_id=current.id,
        requested_setup_id=requested.id,
        column_name="ssd",
        status="COMPLETED",
    )
    db_session.add(legacy_swap)
    db_session.commit()
    db_session.refresh(legacy_swap)

    assert legacy_swap.setup_id is None
    assert legacy_swap.current_setup_id == current.id
    assert legacy_swap.requested_setup_id == requested.id
