"""
Shared pytest fixtures for the Reservation Management System test suite.

CRITICAL: every environment variable that controls where the application
reads/writes data (DATABASE_URL, LOG_DIR, EXPORT_DIR, EXCEL_LOG_DIR) is
overridden to point at a throwaway temporary directory *before* anything is
imported from ``app``. This guarantees the test suite never touches the
real ``reservation_system.db`` file or the real ``logs/`` directory.

Do not import anything from ``app`` above the environment-variable block
below, or the override will be too late (Settings() is a module-level
singleton evaluated at first import).
"""
import os
import shutil
import tempfile

_TEST_TMP_DIR = tempfile.mkdtemp(prefix="rms_test_")

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_TMP_DIR, "test_reservation_system.db")
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["APP_ENV"] = "test"
os.environ["APP_DEBUG"] = "false"
os.environ["DATABASE_ECHO"] = "false"
os.environ["BCRYPT_ROUNDS"] = "4"  # low cost factor: tests hash many passwords
os.environ["ENABLE_SCHEDULER"] = "false"  # no background sweep threads during tests
os.environ["SMTP_ENABLED"] = "false"  # notifications are logged, never sent
os.environ["LOG_DIR"] = os.path.join(_TEST_TMP_DIR, "logs")
os.environ["EXPORT_DIR"] = os.path.join(_TEST_TMP_DIR, "logs", "exports")
os.environ["EXCEL_LOG_DIR"] = os.path.join(_TEST_TMP_DIR, "logs", "excel_logs")
os.environ["CORS_ALLOWED_ORIGINS"] = "http://testserver"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  (registers every model on Base.metadata)
from app.core.constants import RoleName, SetupStatus, UserStatus  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.init_db import seed_roles_and_permissions  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.group import Group  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.setup import Setup  # noqa: E402
from app.models.user import User  # noqa: E402

# Tables whose contents must survive the per-test cleanup (RBAC seed data).
_PRESERVE_TABLES = {"roles", "permissions", "role_permissions"}

_counter = {"n": 0}


def _next_n() -> int:
    """Monotonically increasing counter for building unique test fixture values."""
    _counter["n"] += 1
    return _counter["n"]


# ---------------------------------------------------------------------
# Session-scoped: create schema + seed RBAC data exactly once
# ---------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _test_database_setup():
    """Create every table and seed Roles/Permissions once for the whole test session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles_and_permissions(db)
    finally:
        db.close()

    yield

    engine.dispose()
    shutil.rmtree(_TEST_TMP_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_database():
    """
    After every test, delete all rows from every table except the seeded
    RBAC tables, so tests never see leftover data from earlier tests.
    """
    yield
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in _PRESERVE_TABLES:
                db.execute(table.delete())
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------
# Core fixtures: DB session, FastAPI app, TestClient
# ---------------------------------------------------------------------

@pytest.fixture
def db_session():
    """A direct SQLAlchemy session against the isolated test database, for fixture setup/assertions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def app_instance():
    """The FastAPI application under test."""
    return fastapi_app


@pytest.fixture
def client(app_instance):
    """
    A FastAPI TestClient bound to the real app, wired to the isolated test
    database via the DATABASE_URL override at the top of this module.
    Used as a context manager so startup/shutdown events actually run
    (registers the SQLite FK-enforcement pragma, matching production).
    """
    with TestClient(app_instance) as test_client:
        yield test_client


# ---------------------------------------------------------------------
# Role fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def role_by_name(db_session):
    """Factory: fetch a seeded Role by name."""

    def _get(name: str) -> Role:
        role = db_session.query(Role).filter(Role.name == name).first()
        assert role is not None, "Role '{0}' was not seeded -- check seed_roles_and_permissions.".format(name)
        return role

    return _get


# ---------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def make_user(db_session, role_by_name):
    """
    Factory fixture: directly create an APPROVED, active User with a given
    role (bypassing the registration/approval HTTP flow for fast test setup).
    """

    def _make(
        role_name=RoleName.DEVELOPER,
        group_id=None,
        status=UserStatus.APPROVED,
        is_active=True,
        password="Password123",
        username=None,
        email=None,
    ):
        n = _next_n()
        role = role_by_name(role_name)
        user = User(
            username=username or "user{0}".format(n),
            email=email or "user{0}@example.com".format(n),
            password_hash=hash_password(password),
            full_name="Test User {0}".format(n),
            role_id=role.id,
            group_id=group_id,
            status=status,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture
def developer_user(make_user):
    """A single approved DEVELOPER user (can create reservations, request swaps)."""
    return make_user(role_name=RoleName.DEVELOPER)


@pytest.fixture
def second_developer_user(make_user):
    """A second, distinct approved DEVELOPER user."""
    return make_user(role_name=RoleName.DEVELOPER)


@pytest.fixture
def lead_user(make_user):
    """An approved LEAD user (can approve swaps/registrations within their own group)."""
    return make_user(role_name=RoleName.LEAD)


@pytest.fixture
def owner_user(make_user):
    """An approved OWNER user (full permissions)."""
    return make_user(role_name=RoleName.OWNER)


@pytest.fixture
def plain_user(make_user):
    """An approved plain USER (read-only permissions)."""
    return make_user(role_name=RoleName.USER)


# ---------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------

@pytest.fixture
def auth_headers():
    """Factory: build an ``Authorization: Bearer`` header dict for a given User, minted directly (no HTTP login)."""

    def _headers(user: User) -> dict:
        token = create_access_token(user_id=user.id, role=user.role.name)
        return {"Authorization": "Bearer {0}".format(token)}

    return _headers


@pytest.fixture
def web_login(client):
    """Factory: set the ``access_token`` cookie on the shared TestClient for a given User (web/cookie auth)."""

    def _login(user: User):
        token = create_access_token(user_id=user.id, role=user.role.name)
        client.cookies.set("access_token", token)
        return token

    return _login


# ---------------------------------------------------------------------
# Product / Group / Setup fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def product(db_session):
    """A single Product."""
    n = _next_n()
    obj = Product(name="Product-{0}".format(n), description="Test product {0}".format(n))
    db_session.add(obj)
    db_session.commit()
    db_session.refresh(obj)
    return obj


@pytest.fixture
def group(db_session):
    """A single Group."""
    n = _next_n()
    obj = Group(name="Group-{0}".format(n), description="Test group {0}".format(n))
    db_session.add(obj)
    db_session.commit()
    db_session.refresh(obj)
    return obj


@pytest.fixture
def make_setup(db_session, product):
    """Factory fixture: create a Setup (defaults to AVAILABLE) under the given/default Product."""

    def _make(status=SetupStatus.AVAILABLE, product_id=None, group_id=None, owner_id=None):
        n = _next_n()
        obj = Setup(
            product_id=product_id or product.id,
            group_id=group_id,
            ip_address="10.0.{0}.{1}".format((n // 250) % 250, n % 250 + 1),
            hostname="setup-{0}.example.com".format(n),
            location="Rack {0}".format(n),
            status=status,
            owner_id=owner_id,
        )
        db_session.add(obj)
        db_session.commit()
        db_session.refresh(obj)
        return obj

    return _make


@pytest.fixture
def setup(make_setup):
    """A single AVAILABLE Setup."""
    return make_setup()
