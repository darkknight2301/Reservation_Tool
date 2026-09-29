"""
Phase 6 tests: UI integration -- swap column validity, Original-vs-Current
view, Approvals (pending + history) across Swap and Borrow, borrowed status,
and the lender losing swap access while a setup is lent out.
"""
from datetime import datetime, timedelta

import pytest

from app.core.constants import ApprovalHierarchyScope, RoleName
from app.models.group import Group
from app.models.group_hierarchy_edge import GroupHierarchyEdge
from app.models.product import Product
from app.models.product_template_column import ProductTemplateColumn
from app.models.setup_custom_field_value import SetupCustomFieldValue
from app.models.setup_hardware_baseline import SetupHardwareBaseline

API = "/api/v1"


@pytest.fixture
def world(db_session, make_user, make_setup, product):
    """Groups d (lender), e (borrower), b (approver parent, BORROW b->d) each with a lead, plus a setup owned by d."""
    db = db_session
    g = {n: Group(name="{0}-{1}".format(n, id(db))) for n in "bde"}
    db.add_all(g.values())
    db.flush()
    db.add(GroupHierarchyEdge(parent_group_id=g["b"].id, child_group_id=g["d"].id, scope=ApprovalHierarchyScope.BORROW))
    db.commit()

    class _W:
        pass

    w = _W()
    w.g = g
    w.lead = {n: make_user(role_name=RoleName.LEAD, group_id=g[n].id) for n in "bde"}
    w.setup_d = make_setup(product_id=product.id, group_id=g["d"].id)
    w.setup_e = make_setup(product_id=product.id, group_id=g["e"].id)
    w.product, w.make_setup, w.make_user, w.db = product, make_setup, make_user, db
    return w


def _borrow(client, auth_headers, w):
    resp = client.post(
        API + "/borrows",
        json={"source_lead_id": w.lead["d"].id, "setup_id": w.setup_d.id, "reason": "ui"},
        headers=auth_headers(w.lead["e"]),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------
# Lender loses swap access while lent out
# ---------------------------------------------------------------------

def test_lender_loses_swap_access_while_lent_and_regains_it_on_return(client, auth_headers, world):
    w = world
    member_d = w.make_user(role_name=RoleName.DEVELOPER, group_id=w.g["d"].id)
    member_e = w.make_user(role_name=RoleName.DEVELOPER, group_id=w.g["e"].id)
    other_d = w.make_setup(product_id=w.product.id, group_id=w.g["d"].id)
    swap = {"current_setup_id": w.setup_d.id, "requested_setup_id": other_d.id, "column_names": ["ssd"]}

    assert client.post(API + "/swaps", json=swap, headers=auth_headers(member_d)).status_code == 201   # before

    borrow_id = _borrow(client, auth_headers, w)
    client.patch("{0}/borrows/{1}/approve".format(API, borrow_id), json={}, headers=auth_headers(w.lead["b"]))
    assert client.post(API + "/swaps", json=swap, headers=auth_headers(member_d)).status_code == 403   # lent out

    other_e = {"current_setup_id": w.setup_d.id, "requested_setup_id": w.setup_e.id, "column_names": ["ssd"]}
    assert client.post(API + "/swaps", json=other_e, headers=auth_headers(member_e)).status_code == 201  # borrower can

    client.patch("{0}/borrows/{1}/return".format(API, borrow_id), json={}, headers=auth_headers(w.lead["e"]))
    assert client.post(API + "/swaps", json=swap, headers=auth_headers(member_d)).status_code == 201   # regained


# ---------------------------------------------------------------------
# Swap dialog: only valid columns are selectable
# ---------------------------------------------------------------------

def test_swap_columns_only_selectable_when_present_on_both_setups(client, web_login, world):
    w = world
    other_product = Product(name="Other-{0}".format(id(w.db)), description="x")
    w.db.add(other_product)
    w.db.commit()
    w.db.add_all([
        ProductTemplateColumn(product_id=w.product.id, name="shared_col", label="Shared", data_type="String"),
        ProductTemplateColumn(product_id=w.product.id, name="only_here", label="Only Here", data_type="String"),
        ProductTemplateColumn(product_id=other_product.id, name="shared_col", label="Shared", data_type="String"),
    ])
    w.db.commit()
    partner = w.make_setup(product_id=other_product.id)   # ungrouped => accessible
    user = w.make_user(role_name=RoleName.DEVELOPER)

    web_login(user)
    html = client.get("/setups/swap-dialog/columns", params={"current_setup_id": w.setup_e.id, "requested_setup_id": partner.id}).text
    assert 'value="shared_col"' in html and 'value="ssd"' in html
    only_here = html.split('value="only_here"')[1].split(">")[0]
    assert "disabled" in only_here, "a column missing on the partner setup must not be selectable"
    shared = html.split('value="shared_col"')[1].split(">")[0]
    assert "disabled" not in shared


def test_swap_dialog_has_all_request_fields(client, web_login, world):
    user = world.make_user(role_name=RoleName.DEVELOPER)
    web_login(user)
    html = client.get("/setups/swap-dialog", params={"setup_id": world.setup_e.id}).text
    for needle in ('name="reason"', 'name="start_time"', 'name="end_time"', 'name="announcement_channels"', 'name="announcement_message"', 'name="column_names"'):
        assert needle in html


def test_reserve_and_borrow_dialogs_have_reason_time_announcement_fields(client, web_login, world):
    web_login(world.make_user(role_name=RoleName.DEVELOPER))
    reserve = client.get("/setups/reserve-dialog", params={"setup_ids": str(world.setup_e.id)}).text
    for needle in ("Reason", 'name="reserved_from"', 'name="reserved_until"', 'name="announcement_channels"', "Mail Leads"):
        assert needle in reserve
    web_login(world.lead["e"])
    borrow = client.get("/borrows/request-dialog").text
    for needle in ('name="source_lead_id"', 'name="reason"', 'name="start_time"', 'name="end_time"', 'name="announcement_channels"', "Mail Leads"):
        assert needle in borrow


# ---------------------------------------------------------------------
# Original vs Current + highlighting
# ---------------------------------------------------------------------

def test_hardware_compare_dialog_shows_original_current_changed_and_history(client, web_login, world):
    w = world
    setup = w.setup_e
    setup.ssd = "NEW-SSD"
    setup.hdd = "NEW-HDD"
    w.db.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().hdd = "NEW-HDD"   # hdd unchanged
    w.db.commit()

    web_login(w.make_user(role_name=RoleName.DEVELOPER))
    html = client.get("/setups/{0}/hardware-compare".format(setup.id)).text
    assert "1 field changed" in html
    ssd_row = html.split("<td>Ssd</td>")[1].split("</tr>")[0]
    assert "NEW-SSD" in ssd_row and "rms-cell-changed" in ssd_row
    hdd_row = html.split("<td>Hdd</td>")[1].split("</tr>")[0]
    assert "rms-cell-changed" not in hdd_row
    assert "Change history" in html


def test_table_has_compare_button_and_navigation_shortcuts(client, web_login, world):
    web_login(world.lead["e"])
    html = client.get("/setups").text
    assert "/borrows" in html and "/approvals" in html
    table = client.get("/setups/table").text
    assert "/hardware-compare" in table


def test_borrowed_status_badge_on_setups_table(client, web_login, auth_headers, world):
    w = world
    borrow_id = _borrow(client, auth_headers, w)
    client.patch("{0}/borrows/{1}/approve".format(API, borrow_id), json={}, headers=auth_headers(w.lead["b"]))
    web_login(w.lead["e"])
    html = client.get("/setups/table", params={"group_id": w.g["e"].id}).text
    assert "Borrowed by" in html and w.setup_d.hostname in html


# ---------------------------------------------------------------------
# Approvals: pending + history across Swap and Borrow
# ---------------------------------------------------------------------

def test_approvals_pending_shows_swap_and_borrow_and_only_routed_can_act(client, web_login, auth_headers, world):
    w = world
    _borrow(client, auth_headers, w)
    member_e = w.make_user(role_name=RoleName.DEVELOPER, group_id=w.g["e"].id)
    other_e = w.make_setup(product_id=w.product.id, group_id=w.g["e"].id)
    swap = client.post(API + "/swaps", json={"current_setup_id": w.setup_e.id, "requested_setup_id": other_e.id, "column_names": ["ssd"]},
                       headers=auth_headers(member_e))
    assert swap.status_code == 201

    web_login(w.lead["b"])      # routed borrow approver
    html = client.get("/approvals").text
    assert "Pending Approvals" in html and "BORROW" in html and "SWAP" in html
    assert "/approvals/borrow/" in html and "/approve" in html

    web_login(w.lead["e"])      # the borrow's requester: can cancel, cannot approve their own
    html = client.get("/approvals/content", params={"tab": "pending"}).text
    assert "Cancel my request" in html
    assert "/approve" not in html, "a requester must not be offered Approve on their own request"


def test_approve_from_approvals_page_then_history_shows_decider(client, web_login, auth_headers, world):
    w = world
    borrow_id = _borrow(client, auth_headers, w)
    web_login(w.lead["d"])
    resp = client.post("/approvals/borrow/{0}/approve".format(borrow_id))
    assert resp.status_code == 200
    history = client.get("/approvals/content", params={"tab": "history"}).text
    assert "Approval History" in history and w.lead["d"].full_name in history and "COMPLETED" in history
    assert "Borrower" in history

    web_login(w.lead["e"])
    assert "BORROW" in client.get("/approvals/content", params={"tab": "history", "mine": "true"}).text


def test_reject_from_approvals_page(client, web_login, auth_headers, world):
    w = world
    borrow_id = _borrow(client, auth_headers, w)
    web_login(w.lead["b"])
    assert client.post("/approvals/borrow/{0}/reject".format(borrow_id), data={"rejection_reason": "no"}).status_code == 200
    web_login(w.lead["e"])
    assert "REJECTED" in client.get("/approvals/content", params={"tab": "history"}).text


def test_developers_do_not_see_borrow_items_on_approvals(client, web_login, auth_headers, world):
    w = world
    _borrow(client, auth_headers, w)
    web_login(w.make_user(role_name=RoleName.DEVELOPER))
    html = client.get("/approvals").text
    assert "BORROW" not in html.replace("Borrow / Return", "")
