"""
Frontend tests: server-rendered HTML/Jinja/HTMX responses, exercised purely
through FastAPI's TestClient (no browser automation). Where a behavior is
implemented client-side only (e.g. the Reserve dialog's Preview/Back step
switching is a JS show/hide toggle), we verify the underlying HTML/ids the
JS depends on are present in the server response, and record anything that
genuinely cannot be verified without executing JavaScript as a limitation
(see the bottom of this file).
"""
from datetime import datetime, timedelta

from app.core.constants import RoleName, SetupStatus


def _iso(dt):
    return dt.isoformat()


# ---------------------------------------------------------------------
# Login / Registration pages
# ---------------------------------------------------------------------

def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text
    assert "Login" in response.text


def test_login_page_redirects_when_already_authenticated(client, web_login, developer_user):
    web_login(developer_user)
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


def test_registration_page_renders(client):
    response = client.get("/register")
    assert response.status_code == 200
    for field in ("full_name", "username", "email", "password"):
        assert 'name="{0}"'.format(field) in response.text


def test_registration_submit_shows_pending_message(client):
    response = client.post(
        "/register",
        data={
            "username": "webreguser",
            "email": "webreguser@example.com",
            "full_name": "Web Reg User",
            "password": "Password123",
        },
    )
    assert response.status_code == 200
    assert "administrator must approve your account" in response.text.lower()


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

def test_dashboard_requires_login_redirects(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_dashboard_renders_for_logged_in_user(client, web_login, developer_user):
    web_login(developer_user)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert developer_user.full_name in response.text
    assert "Total Setups" in response.text
    assert "Available Now" in response.text


# ---------------------------------------------------------------------
# Product selection
# ---------------------------------------------------------------------

def test_product_selection_page_lists_products(client, web_login, developer_user, product):
    web_login(developer_user)
    response = client.get("/products")
    assert response.status_code == 200
    assert product.name in response.text


# ---------------------------------------------------------------------
# Reservation table: headers, row state, checkboxes, controls
# ---------------------------------------------------------------------

_REQUIRED_TABLE_HEADERS = [
    "Sr No", "Status", "IP", "Hostname", "User", "Form Factor", "Capacity",
    "Aardvark", "Quarch", "APC", "Remote Server", "Hardware Info", "Adapter",
    "Owner", "Location", "Reserved Time", "Remarks",
]


def test_reservation_table_required_headers_present(client, web_login, developer_user, setup):
    web_login(developer_user)
    response = client.get("/setups")
    assert response.status_code == 200
    for header in _REQUIRED_TABLE_HEADERS:
        assert "<th>{0}</th>".format(header) in response.text, "Missing table header: {0}".format(header)


def test_reservation_table_action_controls_present(client, web_login, developer_user, setup):
    web_login(developer_user)
    response = client.get("/setups")
    assert response.status_code == 200
    assert 'id="reserveActionBtn"' in response.text
    assert 'id="swapActionBtn"' in response.text
    assert 'id="unreserveActionBtn"' in response.text
    # Buttons start disabled until a row is selected (client-side JS then toggles this).
    assert 'id="reserveActionBtn" class="btn btn-success btn-sm" disabled' in response.text


def test_available_setup_row_checkbox_enabled(client, web_login, developer_user, setup):
    assert setup.status == SetupStatus.AVAILABLE
    web_login(developer_user)
    response = client.get("/setups")
    assert response.status_code == 200
    assert 'data-setup-id="{0}"'.format(setup.id) in response.text
    assert 'data-status="AVAILABLE"' in response.text
    row_start = response.text.index('data-setup-id="{0}"'.format(setup.id))
    row_snippet = response.text[row_start : row_start + 600]
    assert "disabled" not in row_snippet.split("</td>")[0]


def test_reserved_setup_row_checkbox_disabled_for_other_user(
    client, web_login, developer_user, second_developer_user, auth_headers, setup
):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    client.post(
        "/api/v1/reservations",
        json={"setup_id": setup.id, "reserved_from": _iso(start), "reserved_until": _iso(end)},
        headers=auth_headers(second_developer_user),
    )

    web_login(developer_user)
    response = client.get("/setups")
    row_start = response.text.index('data-setup-id="{0}"'.format(setup.id))
    row_snippet = response.text[row_start : row_start + 600]
    assert 'data-status="RESERVED"' in row_snippet
    assert 'data-mine="false"' in row_snippet
    assert "disabled" in row_snippet.split("</td>")[0]


def test_reserved_setup_row_checkbox_enabled_for_owning_user(client, web_login, developer_user, auth_headers, setup):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    client.post(
        "/api/v1/reservations",
        json={"setup_id": setup.id, "reserved_from": _iso(start), "reserved_until": _iso(end)},
        headers=auth_headers(developer_user),
    )

    web_login(developer_user)
    response = client.get("/setups")
    row_start = response.text.index('data-setup-id="{0}"'.format(setup.id))
    row_snippet = response.text[row_start : row_start + 600]
    assert 'data-mine="true"' in row_snippet
    assert "disabled" not in row_snippet.split("</td>")[0]


# ---------------------------------------------------------------------
# Reserve dialog + preview step
# ---------------------------------------------------------------------

def test_reserve_dialog_renders_form_and_preview_markup(client, web_login, developer_user, setup):
    web_login(developer_user)
    response = client.get("/setups/reserve-dialog", params={"setup_ids": str(setup.id)})
    assert response.status_code == 200
    assert setup.hostname in response.text
    assert 'name="reserved_from"' in response.text
    assert 'name="reserved_until"' in response.text
    assert 'name="remarks"' in response.text
    for label in ("Wall Message", "Mail Leads", "Groups", "All Users"):
        assert label in response.text
    # Step 2 (preview) markup is present in the server response (hidden via CSS until JS reveals it):
    assert 'id="reserveStepPreview"' in response.text
    assert 'id="previewSetups"' in response.text
    assert 'id="reserveBackBtn"' in response.text
    assert 'id="reserveNextBtn"' in response.text


# ---------------------------------------------------------------------
# Swap dialog
# ---------------------------------------------------------------------

def test_swap_dialog_lists_candidate_setups(client, web_login, developer_user, auth_headers, make_setup, product):
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    create_resp = client.post(
        "/api/v1/reservations",
        json={"setup_id": setup_a.id, "reserved_from": _iso(start), "reserved_until": _iso(end)},
        headers=auth_headers(developer_user),
    )
    reservation_id = create_resp.json()["id"]

    web_login(developer_user)
    response = client.get("/setups/swap-dialog", params={"reservation_id": reservation_id})
    assert response.status_code == 200
    assert setup_a.hostname in response.text
    assert setup_b.hostname in response.text
    assert "requires approval" in response.text.lower()


# ---------------------------------------------------------------------
# Unreserve dialog + pending-swap warning
# ---------------------------------------------------------------------

def test_unreserve_dialog_no_warning_when_no_pending_swap(client, web_login, developer_user, auth_headers, setup):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    create_resp = client.post(
        "/api/v1/reservations",
        json={"setup_id": setup.id, "reserved_from": _iso(start), "reserved_until": _iso(end)},
        headers=auth_headers(developer_user),
    )
    reservation_id = create_resp.json()["id"]

    web_login(developer_user)
    response = client.get("/setups/unreserve-dialog", params={"reservation_ids": str(reservation_id)})
    assert response.status_code == 200
    assert "pending swap request" not in response.text.lower()
    assert "disabled" not in response.text.split('type="submit"')[1].split(">")[0]


def test_unreserve_dialog_shows_warning_when_swap_pending(
    client, web_login, developer_user, auth_headers, make_setup, product
):
    setup_a = make_setup(product_id=product.id)
    setup_b = make_setup(product_id=product.id)
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    dev_headers = auth_headers(developer_user)

    create_resp = client.post(
        "/api/v1/reservations",
        json={"setup_id": setup_a.id, "reserved_from": _iso(start), "reserved_until": _iso(end)},
        headers=dev_headers,
    )
    reservation_id = create_resp.json()["id"]
    client.post(
        "/api/v1/swaps",
        json={"reservation_id": reservation_id, "requested_setup_id": setup_b.id},
        headers=dev_headers,
    )

    web_login(developer_user)
    response = client.get("/setups/unreserve-dialog", params={"reservation_ids": str(reservation_id)})
    assert response.status_code == 200
    assert "pending swap request" in response.text.lower()
    submit_button_segment = response.text.split('type="submit"')[1].split(">")[0]
    assert "disabled" in submit_button_segment


# ---------------------------------------------------------------------
# Role-based controls (navbar visibility)
# ---------------------------------------------------------------------

def test_navbar_hides_admin_links_for_plain_user(client, web_login, plain_user):
    web_login(plain_user)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert 'href="/admin/products"' not in response.text
    assert 'href="/admin/users"' not in response.text
    assert 'href="/admin/logs"' not in response.text
    assert 'href="/admin/developer-logs"' not in response.text


def test_navbar_shows_admin_links_for_owner(client, web_login, owner_user):
    web_login(owner_user)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert 'href="/admin/products"' in response.text
    assert 'href="/admin/users"' in response.text
    assert 'href="/admin/logs"' in response.text
    assert 'href="/admin/developer-logs"' in response.text


def test_admin_products_page_forbidden_for_developer(client, web_login, developer_user):
    web_login(developer_user)
    response = client.get("/admin/products")
    assert response.status_code == 403
    assert "Access Denied" in response.text


def test_admin_products_page_allowed_for_owner(client, web_login, owner_user, product):
    web_login(owner_user)
    response = client.get("/admin/products")
    assert response.status_code == 200
    assert product.name in response.text


# ---------------------------------------------------------------------
# Logs visibility
# ---------------------------------------------------------------------

def test_audit_logs_page_forbidden_for_developer(client, web_login, developer_user):
    web_login(developer_user)
    response = client.get("/admin/logs")
    assert response.status_code == 403


def test_audit_logs_page_allowed_for_dev_lead(client, web_login, make_user):
    dev_lead = make_user(role_name=RoleName.DEVELOPER_LEAD)
    web_login(dev_lead)
    response = client.get("/admin/logs")
    assert response.status_code == 200


def test_developer_logs_page_forbidden_for_plain_developer(client, web_login, developer_user):
    web_login(developer_user)
    response = client.get("/admin/developer-logs")
    assert response.status_code == 403


def test_developer_logs_page_allowed_for_lead(client, web_login, lead_user):
    web_login(lead_user)
    response = client.get("/admin/developer-logs")
    assert response.status_code == 200


# ---------------------------------------------------------------------
# Documented limitation
# ---------------------------------------------------------------------

def test_limitation_reserve_preview_step_switch_is_client_side_js():
    """
    LIMITATION (not a test failure): the Reserve dialog's actual Step-1 ->
    Step-2 switch (hiding #reserveStepForm, revealing #reserveStepPreview,
    populating the preview fields) is performed entirely by JavaScript
    (event listeners on #reserveNextBtn/#reserveBackBtn in the page's
    static JS). FastAPI's TestClient only executes server-side Jinja
    rendering and does not run a JS engine, so this suite can only verify
    that the required HTML/ids/labels the script depends on are present in
    the server response (see test_reserve_dialog_renders_form_and_preview_markup
    above) -- it cannot click the button and assert the visible step
    actually changes. The same limitation applies to the sticky table
    header's CSS-only behavior, the dark-mode toggle, and the client-side
    column-filter/search-as-you-type behavior in table.js.
    """
    assert True
