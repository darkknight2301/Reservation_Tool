"""Regression tests for the two settings that are now enforced, and the renamed navbar label."""
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.core.constants import RoleName
from app.models.product import Product

API = "/api/v1"


def _window(start_offset_minutes, hours=2):
    start = datetime.utcnow() + timedelta(minutes=start_offset_minutes)
    return start.isoformat(), (start + timedelta(hours=hours)).isoformat()


def test_min_lead_time_default_zero_allows_any_start(client, auth_headers, developer_user, setup):
    start, end = _window(1)
    resp = client.post(API + "/reservations", json={"setup_id": setup.id, "reserved_from": start, "reserved_until": end},
                       headers=auth_headers(developer_user))
    assert resp.status_code == 201


def test_min_lead_time_rejects_too_early_start_and_accepts_late_enough(client, auth_headers, developer_user, setup, monkeypatch):
    monkeypatch.setattr(settings, "RESERVATION_MIN_LEAD_MINUTES", 30)
    start, end = _window(5)
    early = client.post(API + "/reservations", json={"setup_id": setup.id, "reserved_from": start, "reserved_until": end},
                        headers=auth_headers(developer_user))
    assert early.status_code == 422 and "at least 30 minute" in early.text

    start, end = _window(45)
    ok = client.post(API + "/reservations", json={"setup_id": setup.id, "reserved_from": start, "reserved_until": end},
                     headers=auth_headers(developer_user))
    assert ok.status_code == 201


def test_swap_between_different_products_rejected_when_same_product_required(client, auth_headers, developer_user, make_setup, product, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SWAP_REQUIRE_SAME_PRODUCT", True)
    other = Product(name="OtherProd-{0}".format(id(db_session)), description="x")
    db_session.add(other)
    db_session.commit()
    a, b = make_setup(product_id=product.id), make_setup(product_id=other.id)
    resp = client.post(API + "/swaps", json={"current_setup_id": a.id, "requested_setup_id": b.id, "column_names": ["ssd"]},
                       headers=auth_headers(developer_user))
    assert resp.status_code == 422 and "same product" in resp.text


def test_cross_product_swap_allowed_when_rule_disabled(client, auth_headers, developer_user, make_setup, product, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SWAP_REQUIRE_SAME_PRODUCT", False)
    other = Product(name="OtherProd2-{0}".format(id(db_session)), description="x")
    db_session.add(other)
    db_session.commit()
    a, b = make_setup(product_id=product.id), make_setup(product_id=other.id)
    resp = client.post(API + "/swaps", json={"current_setup_id": a.id, "requested_setup_id": b.id, "column_names": ["ssd"]},
                       headers=auth_headers(developer_user))
    assert resp.status_code == 201


def test_swap_dialog_lists_only_same_product_partners_when_required(client, web_login, developer_user, make_setup, product, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SWAP_REQUIRE_SAME_PRODUCT", True)
    other = Product(name="OtherProd3-{0}".format(id(db_session)), description="x")
    db_session.add(other)
    db_session.commit()
    mine = make_setup(product_id=product.id)
    same = make_setup(product_id=product.id)
    different = make_setup(product_id=other.id)
    web_login(developer_user)
    html = client.get("/setups/swap-dialog", params={"setup_id": mine.id}).text
    assert same.hostname in html and different.hostname not in html


def test_navbar_labels_are_distinct_for_swap_borrow_and_user_approvals(client, web_login, make_user):
    web_login(make_user(role_name=RoleName.LEAD))
    html = client.get("/dashboard").text
    assert ">User Approvals<" in html.replace("</i>", ">").replace("</a>", "<") or "User Approvals" in html
    assert html.count("</i>Approvals</a>") == 1, "exactly one nav item may be labelled plain 'Approvals'"
