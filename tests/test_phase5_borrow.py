"""
Phase 5 tests: Borrow (independent of Reservation and Swap), plus the
Setup Edit re-baseline decision.

Routing scenario (business-rule Borrow example, Group 2):
    a -> d,e ; b -> d,f,g ; c -> h,i,b     (all BORROW-scoped edges)
    "E requests Borrow from d" -> approval goes to b, d, f, g (any ONE suffices).
"""
from datetime import datetime, timedelta

import pytest

from app.core.constants import ApprovalHierarchyScope, BorrowStatus, RoleName, SetupStatus
from app.core.exceptions import AuthorizationError, ConflictError, ValidationAppError
from app.models.group import Group
from app.models.group_hierarchy_edge import GroupHierarchyEdge
from app.models.setup_access_grant import SetupAccessGrant
from app.models.setup_hardware_baseline import SetupHardwareBaseline
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.borrow_repository import BorrowRepository
from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
from app.repositories.sqlalchemy.hardware_baseline_repository import HardwareBaselineRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.repositories.sqlalchemy.user_repository import UserRepository
from app.schemas.borrow_request import BorrowCreateRequest, BorrowDecisionRequest, BorrowReturnRequest
from app.schemas.setup import SetupFilter
from app.services.approval_routing_service import ApprovalRoutingService
from app.services.audit_service import AuditService
from app.services.borrow_service import BorrowService
from app.services.hardware_state_service import HardwareStateService

API = "/api/v1"


class _FakeNotifier:
    """Records what would have been emailed / broadcast."""

    def __init__(self):
        self.emails = []
        self.broadcasts = []

    def email_direct(self, recipients, subject, message):
        self.emails.append((sorted(recipients), subject, message))

    def broadcast_reservation_event(self, channels, message, setup, acting_user):
        self.broadcasts.append((list(channels), message))


@pytest.fixture
def env(db_session, make_user, make_setup, product):
    db = db_session
    groups = {n: Group(name="{0}-{1}".format(n, id(db))) for n in "abcdefghi"}
    db.add_all(groups.values())
    db.flush()
    edges = [("a", "d"), ("a", "e"), ("b", "d"), ("b", "f"), ("b", "g"), ("c", "h"), ("c", "i"), ("c", "b")]
    db.add_all([
        GroupHierarchyEdge(parent_group_id=groups[p].id, child_group_id=groups[c].id, scope=ApprovalHierarchyScope.BORROW)
        for p, c in edges
    ])
    db.commit()

    leads = {n: make_user(role_name=RoleName.LEAD, group_id=groups[n].id) for n in "abcdefg"}
    notifier = _FakeNotifier()
    audit = AuditService(AuditLogRepository(db))
    service = BorrowService(
        BorrowRepository(db), SetupRepository(db), UserRepository(db), audit,
        ApprovalRoutingService(GroupHierarchyRepository(db), UserRepository(db)),
        None, notifier, HardwareStateService(HardwareBaselineRepository(db)),
    )

    class _E:
        pass

    e = _E()
    e.groups, e.leads, e.service, e.notifier, e.db = groups, leads, service, notifier, db
    e.setup_d = make_setup(product_id=product.id, group_id=groups["d"].id)
    e.make_setup, e.product, e.make_user = make_setup, product, make_user
    return e


def _future(hours=2):
    return datetime.utcnow() + timedelta(hours=hours)


def _request(env, setup=None, requester=None, lead=None, **kwargs):
    return env.service.create(
        BorrowCreateRequest(
            source_lead_id=(lead or env.leads["d"]).id, setup_id=(setup or env.setup_d).id, **kwargs
        ),
        requester or env.leads["e"],
    )


# ---------------------------------------------------------------------
# Routing + approval
# ---------------------------------------------------------------------

def test_e_borrowing_from_d_routes_to_b_d_f_g_and_notifies_them(env):
    borrow = _request(env, reason="need quarch", end_time=_future())
    expected = sorted(env.leads[n].email for n in "bdfg")
    assert sorted(borrow.routed_approver_emails.split(",")) == expected
    assert borrow.status == BorrowStatus.PENDING
    assert env.notifier.emails[0][0] == expected  # "lead emails"
    assert borrow.source_group_id == env.groups["d"].id and borrow.target_group_id == env.groups["e"].id


@pytest.mark.parametrize("approver", ["b", "d", "f", "g"])
def test_any_one_routed_approver_is_sufficient(env, approver):
    borrow = _request(env)
    approved = env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads[approver])
    assert approved.status == BorrowStatus.COMPLETED
    assert approved.approved_by_id == env.leads[approver].id


def test_lead_outside_the_routed_set_cannot_approve(env):
    borrow = _request(env)
    for outsider in ("a", "c"):
        with pytest.raises(AuthorizationError):
            env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads[outsider])


def test_requester_cannot_decide_their_own_request(env):
    # b is routed for d, so let b be the requester of a setup owned by d.
    borrow = _request(env, requester=env.leads["b"])
    assert env.leads["b"].email not in borrow.routed_approver_emails.split(",")
    with pytest.raises(AuthorizationError):
        env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["b"])


def test_owner_can_always_approve(env, make_user):
    borrow = _request(env)
    owner = make_user(role_name=RoleName.OWNER)
    assert env.service.approve(borrow.id, BorrowDecisionRequest(), owner).status == BorrowStatus.COMPLETED


def test_reject_and_cancel(env):
    first = _request(env)
    rejected = env.service.reject(first.id, BorrowDecisionRequest(reason="in use"), env.leads["f"])
    assert rejected.status == BorrowStatus.REJECTED
    assert not env.db.query(SetupAccessGrant).count()

    second = _request(env)
    with pytest.raises(AuthorizationError):
        env.service.cancel(second.id, env.leads["d"])
    assert env.service.cancel(second.id, env.leads["e"]).status == BorrowStatus.CANCELLED
    with pytest.raises(ConflictError):
        env.service.approve(second.id, BorrowDecisionRequest(), env.leads["d"])


# ---------------------------------------------------------------------
# Effective state applied, original preserved, history kept
# ---------------------------------------------------------------------

def test_approval_grants_effective_access_but_preserves_original_state(env):
    setup = env.setup_d
    setup.ssd = "ORIG-SSD"
    env.db.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().ssd = "ORIG-SSD"
    env.db.commit()

    borrow = _request(env, hardware_field_name="ssd")
    env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])

    env.db.refresh(setup)
    assert setup.group_id == env.groups["d"].id            # ORIGINAL owner untouched
    assert setup.ssd == "ORIG-SSD"                          # hardware values untouched
    grant = env.db.query(SetupAccessGrant).filter_by(setup_id=setup.id).one()
    assert grant.is_active and grant.granted_to_group_id == env.groups["e"].id
    assert env.db.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().ssd == "ORIG-SSD"

    repo = SetupRepository(env.db)
    assert setup.id in [s.id for s in repo.list(SetupFilter(group_id=env.groups["e"].id), 1, 50)[0]]   # effective holder
    assert setup.id not in [s.id for s in repo.list(SetupFilter(group_id=env.groups["d"].id), 1, 50)[0]]
    assert repo.get_active_grant_group_ids(setup.id) == [env.groups["e"].id]


def test_return_restores_access_notifies_and_keeps_history(env):
    borrow = _request(env, announcement_channels=["WALL", "MAIL_ALL"])
    env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])
    env.notifier.emails.clear()
    env.notifier.broadcasts.clear()

    returned = env.service.return_borrow(borrow.id, BorrowReturnRequest(note="done"), env.leads["e"])
    assert returned.status == BorrowStatus.RETURNED
    assert returned.returned_by_id == env.leads["e"].id and returned.returned_at is not None

    grant = env.db.query(SetupAccessGrant).filter_by(setup_id=env.setup_d.id).one()   # kept, not deleted
    assert grant.is_active is False and grant.returned_at is not None
    repo = SetupRepository(env.db)
    assert repo.get_active_grant_group_ids(env.setup_d.id) == []
    assert env.setup_d.id in [s.id for s in repo.list(SetupFilter(group_id=env.groups["d"].id), 1, 50)[0]]

    recipients, subject, message = env.notifier.emails[0]
    assert env.leads["e"].email in recipients and env.leads["d"].email in recipients
    assert "returned" in subject.lower() and "done" in message
    assert env.notifier.broadcasts and set(env.notifier.broadcasts[0][0]) == {"WALL", "MAIL_ALL"}


def test_source_side_lead_can_get_it_back_but_unrelated_lead_cannot(env):
    borrow = _request(env)
    env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])
    with pytest.raises(AuthorizationError):
        env.service.return_borrow(borrow.id, BorrowReturnRequest(), env.leads["a"])
    assert env.service.return_borrow(borrow.id, BorrowReturnRequest(), env.leads["g"]).status == BorrowStatus.RETURNED


def test_cannot_return_twice_or_return_a_pending_borrow(env):
    borrow = _request(env)
    with pytest.raises(ConflictError):
        env.service.return_borrow(borrow.id, BorrowReturnRequest(), env.leads["e"])
    env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])
    env.service.return_borrow(borrow.id, BorrowReturnRequest(), env.leads["e"])
    with pytest.raises(ConflictError):
        env.service.return_borrow(borrow.id, BorrowReturnRequest(), env.leads["e"])


def test_setup_can_be_borrowed_again_after_return_and_history_lists_both(env):
    first = _request(env)
    env.service.approve(first.id, BorrowDecisionRequest(), env.leads["d"])
    env.service.return_borrow(first.id, BorrowReturnRequest(), env.leads["e"])
    second = _request(env, requester=env.leads["f"])
    assert second.id != first.id
    from app.schemas.borrow_request import BorrowFilter
    items, total = env.service.list(BorrowFilter(setup_id=env.setup_d.id), 1, 50)
    assert total == 2


# ---------------------------------------------------------------------
# Invalid / duplicate / conflicting states
# ---------------------------------------------------------------------

def test_duplicate_pending_or_active_borrow_on_same_setup_is_rejected(env):
    first = _request(env)
    with pytest.raises(ConflictError):
        _request(env, requester=env.leads["f"])          # pending duplicate
    env.service.approve(first.id, BorrowDecisionRequest(), env.leads["d"])
    with pytest.raises(ConflictError):
        _request(env, requester=env.leads["f"])          # already borrowed


def test_cannot_borrow_own_groups_setup_or_unavailable_setup_or_wrong_lead(env):
    own = env.make_setup(product_id=env.product.id, group_id=env.groups["e"].id)
    with pytest.raises(ValidationAppError):
        _request(env, setup=own, lead=env.leads["d"])     # not the selected lead's group
    with pytest.raises(ConflictError):
        _request(env, setup=own, lead=env.leads["e"], requester=env.leads["e"])   # your own group's setup

    maintenance = env.make_setup(product_id=env.product.id, group_id=env.groups["d"].id, status=SetupStatus.MAINTENANCE)
    with pytest.raises(ConflictError):
        _request(env, setup=maintenance)


def test_only_lead_manager_roles_can_request(env, make_user):
    developer = make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["e"].id)
    with pytest.raises(AuthorizationError):
        _request(env, requester=developer)
    no_group_lead = make_user(role_name=RoleName.LEAD)
    with pytest.raises(ValidationAppError):
        _request(env, requester=no_group_lead)


def test_source_must_be_an_active_lead(env, make_user):
    developer = make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["d"].id)
    with pytest.raises(ValidationAppError):
        _request(env, lead=developer)


def test_time_window_validation_and_unknown_hardware_field(env):
    with pytest.raises(ValidationAppError):
        _request(env, end_time=datetime.utcnow() - timedelta(hours=1))
    with pytest.raises(ValueError):
        BorrowCreateRequest(source_lead_id=1, setup_id=1, start_time=_future(3), end_time=_future(1))
    with pytest.raises(ValidationAppError):
        _request(env, hardware_field_name="not_a_field")
    assert _request(env, hardware_field_name="quarch").hardware_field_name == "quarch"


def test_stale_pending_borrow_expires_and_cannot_be_approved(env):
    borrow = _request(env, end_time=_future(1))
    assert env.service.expire_stale_pending(datetime.utcnow() + timedelta(hours=3)) == 1
    assert env.service.get_by_id(borrow.id).status == BorrowStatus.EXPIRED
    with pytest.raises(ConflictError):
        env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])


def test_approval_is_blocked_if_setup_became_unavailable_or_changed_group(env):
    borrow = _request(env)
    env.setup_d.status = SetupStatus.MAINTENANCE
    env.db.commit()
    with pytest.raises(ConflictError):
        env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])


# ---------------------------------------------------------------------
# API / access effects / independence
# ---------------------------------------------------------------------

def test_api_borrow_flow_end_to_end_and_developer_forbidden(client, auth_headers, env):
    developer = env.make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["e"].id)
    payload = {"source_lead_id": env.leads["d"].id, "setup_id": env.setup_d.id, "reason": "need it",
               "hardware_field_name": "quarch", "announcement_channels": ["MAIL_LEADS"]}
    assert client.post(API + "/borrows", json=payload, headers=auth_headers(developer)).status_code == 403

    created = client.post(API + "/borrows", json=payload, headers=auth_headers(env.leads["e"]))
    assert created.status_code == 201, created.text
    borrow_id = created.json()["id"]

    assert client.patch("{0}/borrows/{1}/approve".format(API, borrow_id), json={}, headers=auth_headers(env.leads["a"])).status_code == 403
    approved = client.patch("{0}/borrows/{1}/approve".format(API, borrow_id), json={}, headers=auth_headers(env.leads["f"]))
    assert approved.status_code == 200 and approved.json()["status"] == "COMPLETED"

    dup = client.post(API + "/borrows", json=payload, headers=auth_headers(env.leads["e"]))
    assert dup.status_code == 409

    returned = client.patch("{0}/borrows/{1}/return".format(API, borrow_id), json={"note": "ok"}, headers=auth_headers(env.leads["e"]))
    assert returned.status_code == 200 and returned.json()["status"] == "RETURNED"

    history = client.get(API + "/borrows", params={"setup_id": env.setup_d.id}, headers=auth_headers(env.leads["d"]))
    assert history.status_code == 200 and history.json()["total_items"] == 1


def test_borrow_does_not_touch_reservations_and_is_independent_of_them(client, auth_headers, env):
    member_d = env.make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["d"].id)
    start = datetime.utcnow() + timedelta(hours=1)
    reserved = client.post(
        API + "/reservations",
        json={"setup_id": env.setup_d.id, "reserved_from": start.isoformat(), "reserved_until": (start + timedelta(hours=2)).isoformat()},
        headers=auth_headers(member_d),
    )
    assert reserved.status_code == 201

    borrow = client.post(API + "/borrows", json={"source_lead_id": env.leads["d"].id, "setup_id": env.setup_d.id},
                         headers=auth_headers(env.leads["e"])).json()
    client.patch("{0}/borrows/{1}/approve".format(API, borrow["id"]), json={}, headers=auth_headers(env.leads["d"]))

    reservation = client.get("{0}/reservations/{1}".format(API, reserved.json()["id"]), headers=auth_headers(member_d)).json()
    assert reservation["status"] == "ACTIVE"          # untouched by the borrow
    client.patch("{0}/borrows/{1}/return".format(API, borrow["id"]), json={}, headers=auth_headers(env.leads["e"]))
    reservation = client.get("{0}/reservations/{1}".format(API, reserved.json()["id"]), headers=auth_headers(member_d)).json()
    assert reservation["status"] == "ACTIVE"


def test_borrowing_group_gains_swap_access_only_while_borrowed(client, auth_headers, env):
    member_e = env.make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["e"].id)
    own = env.make_setup(product_id=env.product.id, group_id=env.groups["e"].id)
    swap = {"current_setup_id": own.id, "requested_setup_id": env.setup_d.id, "column_names": ["ssd"]}
    assert client.post(API + "/swaps", json=swap, headers=auth_headers(member_e)).status_code == 403

    borrow = _request(env)
    env.service.approve(borrow.id, BorrowDecisionRequest(), env.leads["d"])
    env.db.commit()
    assert client.post(API + "/swaps", json=swap, headers=auth_headers(member_e)).status_code == 201


# ---------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------

def test_web_borrow_page_is_lead_only_and_full_flow_works(client, web_login, env, make_user):
    web_login(make_user(role_name=RoleName.DEVELOPER, group_id=env.groups["e"].id))
    assert client.get("/borrows").status_code == 403

    web_login(env.leads["e"])
    page = client.get("/borrows")
    assert page.status_code == 200 and "New Borrow Request" in page.text
    dialog = client.get("/borrows/request-dialog")
    assert dialog.status_code == 200 and env.leads["d"].full_name in dialog.text
    partial = client.get("/borrows/request-dialog/setups", params={"source_lead_id": env.leads["d"].id})
    assert env.setup_d.hostname in partial.text and "Quarch" in partial.text

    submit = client.post("/borrows/request", data={"source_lead_id": env.leads["d"].id, "setup_id": env.setup_d.id,
                                                   "hardware_field_name": "quarch", "reason": "web"})
    assert submit.status_code == 200 and "Pending approval" in submit.text and env.setup_d.hostname in submit.text
    borrow = BorrowRepository(env.db).get_open_for_setup(env.setup_d.id)
    assert borrow is not None and borrow.reason == "web"

    web_login(env.leads["g"])
    assert client.post("/borrows/{0}/approve".format(borrow.id)).status_code == 200
    env.db.expire_all()
    assert BorrowRepository(env.db).get_by_id(borrow.id).status == BorrowStatus.COMPLETED

    web_login(env.leads["e"])
    table = client.get("/setups/table", params={"group_id": env.groups["e"].id, "product_id": env.product.id})
    assert "Borrowed by" in table.text
    assert "Return / Get back" in client.get("/borrows").text
    assert client.post("/borrows/{0}/return".format(borrow.id), data={"note": "thanks"}).status_code == 200
    env.db.expire_all()
    assert BorrowRepository(env.db).get_by_id(borrow.id).status == BorrowStatus.RETURNED


# ---------------------------------------------------------------------
# Setup Edit re-baseline (decision: an admin edit becomes the new original)
# ---------------------------------------------------------------------

def test_setup_edit_via_api_rebaselines_only_the_edited_field(client, auth_headers, owner_user, make_setup, db_session):
    setup = make_setup()
    # A swap-style change on hdd (differs from its baseline) must stay highlighted.
    setup.hdd = "SWAPPED-IN-HDD"
    db_session.commit()
    state = HardwareStateService(HardwareBaselineRepository(db_session))
    assert state.changed_fields([setup]) == {setup.id: ["hdd"]}

    resp = client.patch("{0}/setups/{1}".format(API, setup.id), json={"ssd": "EDITED-SSD"}, headers=auth_headers(owner_user))
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().ssd == "EDITED-SSD"
    assert state.changed_fields([setup]) == {setup.id: ["hdd"]}     # edited ssd no longer 'changed'; hdd still is


def test_setup_edit_via_web_form_rebaselines_edited_fields(client, web_login, owner_user, setup, db_session):
    web_login(owner_user)
    form = {"ip_address": setup.ip_address, "hostname": setup.hostname, "location": setup.location, "ssd": "WEB-EDIT-SSD"}
    assert client.post("/setups/{0}/save".format(setup.id), data=form).status_code == 200
    db_session.expire_all()
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().ssd == "WEB-EDIT-SSD"
    state = HardwareStateService(HardwareBaselineRepository(db_session))
    assert state.changed_fields([db_session.get(type(setup), setup.id)]) == {}
