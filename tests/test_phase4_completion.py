"""
Phase 4 completion tests: Original-vs-Current hardware state, generic
changed-field detection (fixed + custom columns), reservation-independent
Swap authorisation, and the table's changed-cell highlighting.
"""
import pytest

from app.core.constants import RoleName
from app.core.exceptions import AuthorizationError
from app.models.group import Group
from app.models.hardware_change_log import HardwareChangeLog
from app.models.product_template_column import ProductTemplateColumn
from app.models.setup_custom_field_baseline import SetupCustomFieldBaseline
from app.models.setup_custom_field_value import SetupCustomFieldValue
from app.models.setup_hardware_baseline import BASELINE_FIELD_NAMES, SetupHardwareBaseline
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.group_hierarchy_repository import GroupHierarchyRepository
from app.repositories.sqlalchemy.hardware_baseline_repository import HardwareBaselineRepository
from app.repositories.sqlalchemy.hardware_change_log_repository import HardwareChangeLogRepository
from app.repositories.sqlalchemy.product_repository import ProductRepository
from app.repositories.sqlalchemy.reservation_repository import ReservationRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.repositories.sqlalchemy.swap_repository import SwapRepository
from app.repositories.sqlalchemy.template_repository import TemplateRepository
from app.repositories.sqlalchemy.user_repository import UserRepository
from app.schemas.swap_request import SwapCreateRequest, SwapDecisionRequest
from app.services.approval_routing_service import ApprovalRoutingService
from app.services.audit_service import AuditService
from app.services.hardware_state_service import HardwareStateService
from app.services.swap_service import SwapService
from app.services.template_service import TemplateService


@pytest.fixture
def svc(db_session):
    audit = AuditService(AuditLogRepository(db_session))
    setup_repo = SetupRepository(db_session)
    state = HardwareStateService(HardwareBaselineRepository(db_session))
    template = TemplateService(TemplateRepository(db_session), ProductRepository(db_session), audit)
    swap = SwapService(
        SwapRepository(db_session), ReservationRepository(db_session), setup_repo, audit,
        HardwareChangeLogRepository(db_session),
        ApprovalRoutingService(GroupHierarchyRepository(db_session), UserRepository(db_session)),
        template, None, state,
    )

    class _S:
        pass

    b = _S()
    b.swap, b.state, b.template, b.setup_repo = swap, state, template, setup_repo
    return b


def _custom_column(db_session, product, name="fw_version"):
    column = ProductTemplateColumn(product_id=product.id, name=name, label=name, data_type="String")
    db_session.add(column)
    db_session.commit()
    return column


# ---------------------------------------------------------------------
# Baseline capture
# ---------------------------------------------------------------------

def test_baseline_is_captured_automatically_for_a_new_setup(db_session, make_setup):
    setup = make_setup()
    baseline = db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one()
    assert baseline is not None
    assert set(BASELINE_FIELD_NAMES) >= {"ssd", "hdd", "capacity"}


def test_custom_baseline_is_captured_on_first_value(db_session, make_setup, product):
    setup = make_setup(product_id=product.id)
    column = _custom_column(db_session, product)
    db_session.add(SetupCustomFieldValue(setup_id=setup.id, template_column_id=column.id, value="v1"))
    db_session.commit()
    baseline = db_session.query(SetupCustomFieldBaseline).filter_by(setup_id=setup.id).one()
    assert baseline.value == "v1"

    # A later edit changes CURRENT only; the baseline row is untouched.
    value = db_session.query(SetupCustomFieldValue).filter_by(setup_id=setup.id).one()
    value.value = "v2"
    db_session.commit()
    assert db_session.query(SetupCustomFieldBaseline).filter_by(setup_id=setup.id).one().value == "v1"


# ---------------------------------------------------------------------
# Changed-field detection (Original vs Current)
# ---------------------------------------------------------------------

def test_no_changes_means_no_changed_fields(svc, make_setup):
    setup = make_setup()
    assert svc.state.changed_fields([setup]) == {}


def test_one_changed_field_is_reported_alone(svc, db_session, make_setup):
    setup = make_setup()
    setup.ssd = "NVMe-X"
    db_session.commit()
    assert svc.state.changed_fields([setup]) == {setup.id: ["ssd"]}


def test_multiple_changed_fields_are_each_reported(svc, db_session, make_setup, product):
    setup = make_setup(product_id=product.id)
    column = _custom_column(db_session, product)
    db_session.add(SetupCustomFieldValue(setup_id=setup.id, template_column_id=column.id, value="v1"))
    db_session.commit()

    setup.ssd = "S"
    setup.hdd = "H"
    db_session.query(SetupCustomFieldValue).filter_by(setup_id=setup.id).one().value = "v2"
    db_session.commit()

    changed = svc.state.changed_fields([setup])[setup.id]
    assert sorted(changed) == ["fw_version", "hdd", "ssd"]


def test_blank_and_none_are_not_a_change(svc, db_session, make_setup):
    setup = make_setup()
    setup.ssd = "  "
    db_session.commit()
    assert svc.state.changed_fields([setup]) == {}


# ---------------------------------------------------------------------
# Swap: reservation-independent authorisation
# ---------------------------------------------------------------------

def test_swap_requires_group_access_not_a_reservation(svc, db_session, make_user, make_setup, product):
    g1, g2 = Group(name="g-own", description="d"), Group(name="g-other", description="d")
    db_session.add_all([g1, g2])
    db_session.commit()
    a = make_setup(product_id=product.id, group_id=g1.id)
    b = make_setup(product_id=product.id, group_id=g1.id)
    member = make_user(role_name=RoleName.DEVELOPER, group_id=g1.id)
    outsider = make_user(role_name=RoleName.DEVELOPER, group_id=g2.id)

    swap = svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), member)
    assert swap.reservation_id is None
    with pytest.raises(AuthorizationError):
        svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), outsider)


def test_swap_requires_access_to_both_setups(svc, db_session, make_user, make_setup, product):
    g1, g2 = Group(name="g-a", description="d"), Group(name="g-b", description="d")
    db_session.add_all([g1, g2])
    db_session.commit()
    a = make_setup(product_id=product.id, group_id=g1.id)
    b = make_setup(product_id=product.id, group_id=g2.id)
    member = make_user(role_name=RoleName.DEVELOPER, group_id=g1.id)
    with pytest.raises(AuthorizationError):
        svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), member)


# ---------------------------------------------------------------------
# Swap: baseline preserved, current updated, changes detected
# ---------------------------------------------------------------------

def test_fixed_field_swap_preserves_baseline_and_flags_only_that_field(svc, db_session, make_user, make_setup, product):
    a, b = make_setup(product_id=product.id), make_setup(product_id=product.id)
    a.ssd, b.ssd = "SSD-A", "SSD-B"
    db_session.commit()
    # The baselines were captured at creation (ssd was NULL); pin them to the values under test.
    for setup in (a, b):
        db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().ssd = setup.ssd
    db_session.commit()

    user = make_user(role_name=RoleName.DEVELOPER)
    swap = svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), user)
    svc.swap.approve(swap.id, SwapDecisionRequest(), make_user(role_name=RoleName.LEAD))

    db_session.refresh(a)
    db_session.refresh(b)
    assert (a.ssd, b.ssd) == ("SSD-B", "SSD-A")
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=a.id).one().ssd == "SSD-A"
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=b.id).one().ssd == "SSD-B"
    assert svc.state.changed_fields([a, b]) == {a.id: ["ssd"], b.id: ["ssd"]}


def test_rejected_swap_changes_nothing(svc, db_session, make_user, make_setup, product):
    a, b = make_setup(product_id=product.id), make_setup(product_id=product.id)
    user = make_user(role_name=RoleName.DEVELOPER)
    swap = svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), user)
    svc.swap.reject(swap.id, SwapDecisionRequest(), make_user(role_name=RoleName.LEAD))
    assert svc.state.changed_fields([a, b]) == {}
    assert db_session.query(HardwareChangeLog).count() == 0


def test_custom_column_swap_captures_baseline_logs_history_and_flags_the_column(svc, db_session, make_user, make_setup, product):
    column = _custom_column(db_session, product)
    a, b = make_setup(product_id=product.id), make_setup(product_id=product.id)
    db_session.add_all([
        SetupCustomFieldValue(setup_id=a.id, template_column_id=column.id, value="A-val"),
        SetupCustomFieldValue(setup_id=b.id, template_column_id=column.id, value="B-val"),
    ])
    db_session.commit()

    user = make_user(role_name=RoleName.DEVELOPER)
    swap = svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["fw_version"]), user)
    svc.swap.approve(swap.id, SwapDecisionRequest(), make_user(role_name=RoleName.LEAD))

    current = {v.setup_id: v.value for v in db_session.query(SetupCustomFieldValue).all()}
    assert current == {a.id: "B-val", b.id: "A-val"}
    baselines = {r.setup_id: r.value for r in db_session.query(SetupCustomFieldBaseline).all()}
    assert baselines == {a.id: "A-val", b.id: "B-val"}
    assert svc.state.changed_fields([a, b]) == {a.id: ["fw_version"], b.id: ["fw_version"]}

    logs = db_session.query(HardwareChangeLog).filter_by(source_request_id=swap.id).all()
    assert {(l.setup_id, l.field_name, l.old_value, l.new_value) for l in logs} == {
        (a.id, "fw_version", "A-val", "B-val"), (b.id, "fw_version", "B-val", "A-val"),
    }


def test_swap_captures_missing_legacy_baseline_before_changing(svc, db_session, make_user, make_setup, product):
    a, b = make_setup(product_id=product.id), make_setup(product_id=product.id)
    a.ssd, b.ssd = "LEG-A", "LEG-B"
    db_session.query(SetupHardwareBaseline).delete()  # simulate legacy rows with no baseline
    db_session.commit()

    user = make_user(role_name=RoleName.DEVELOPER)
    swap = svc.swap.create(SwapCreateRequest(current_setup_id=a.id, requested_setup_id=b.id, column_names=["ssd"]), user)
    svc.swap.approve(swap.id, SwapDecisionRequest(), make_user(role_name=RoleName.LEAD))
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=a.id).one().ssd == "LEG-A"


# ---------------------------------------------------------------------
# UI: only changed cells are highlighted, generically
# ---------------------------------------------------------------------

def test_table_highlights_only_changed_cells(client, web_login, developer_user, db_session, setup):
    setup.ssd = "NEW-SSD"
    setup.quarch = "NEW-QUARCH"
    setup.capacity = "UNCHANGED-IF-BASELINE-MATCHES"
    db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).one().capacity = "UNCHANGED-IF-BASELINE-MATCHES"
    db_session.commit()

    web_login(developer_user)
    html = client.get("/setups/table").text
    assert html.count("rms-cell-changed") == 2
    assert "rms-cell-changed" in html.split("NEW-SSD")[0].rsplit("<td", 1)[1]
    assert "rms-cell-changed" in html.split("NEW-QUARCH")[0].rsplit("<td", 1)[1]
    assert "rms-cell-changed" not in html.split("UNCHANGED-IF-BASELINE-MATCHES")[0].rsplit("<td", 1)[1]


def test_table_has_no_highlight_for_untouched_setup(client, web_login, developer_user, setup):
    web_login(developer_user)
    assert "rms-cell-changed" not in client.get("/setups/table").text.replace("td.rms-cell-changed", "")


def test_deleting_a_setup_also_removes_its_baseline_rows(db_session, make_setup, product):
    setup = make_setup(product_id=product.id)
    column = _custom_column(db_session, product)
    db_session.add(SetupCustomFieldValue(setup_id=setup.id, template_column_id=column.id, value="v"))
    db_session.commit()
    assert db_session.query(SetupHardwareBaseline).filter_by(setup_id=setup.id).count() == 1

    SetupRepository(db_session).delete(setup.id)
    db_session.commit()
    assert db_session.query(SetupHardwareBaseline).count() == 0
    assert db_session.query(SetupCustomFieldBaseline).count() == 0
