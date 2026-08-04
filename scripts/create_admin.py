"""
One-shot script: seeds roles/permissions and creates the initial OWNER
account from ``SEED_ADMIN_*`` settings, if it does not already exist.

Usage:
    python -m scripts.create_admin
"""
import sys
from datetime import datetime
from os.path import abspath, dirname

sys.path.insert(0, dirname(dirname(abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.constants import RoleName, UserStatus  # noqa: E402
from app.core.logging_config import get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.init_db import seed_roles_and_permissions  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    """Create all tables (if absent), seed RBAC data, and create the Owner account."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_roles_and_permissions(db)

        existing = db.query(User).filter(User.username == settings.SEED_ADMIN_USERNAME).first()
        if existing is not None:
            logger.info("Admin user '{0}' already exists; skipping creation.".format(settings.SEED_ADMIN_USERNAME))
            return

        owner_role = db.query(Role).filter(Role.name == RoleName.OWNER).first()
        if owner_role is None:
            raise RuntimeError("OWNER role was not seeded; cannot create admin user.")

        admin_user = User(
            username=settings.SEED_ADMIN_USERNAME,
            email=settings.SEED_ADMIN_EMAIL,
            password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
            full_name=settings.SEED_ADMIN_FULL_NAME,
            role_id=owner_role.id,
            status=UserStatus.APPROVED,
            is_active=True,
            approved_at=datetime.utcnow(),
        )
        db.add(admin_user)
        db.commit()
        logger.info("Created initial OWNER account '{0}'.".format(settings.SEED_ADMIN_USERNAME))
    finally:
        db.close()


if __name__ == "__main__":
    main()
