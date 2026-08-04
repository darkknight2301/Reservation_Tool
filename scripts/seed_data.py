"""
Optional script: seeds a small set of sample Products, Groups, and Setups
for local development/demo purposes. Safe to re-run (idempotent per name).

Usage:
    python -m scripts.seed_data
"""
import sys
from os.path import abspath, dirname

sys.path.insert(0, dirname(dirname(abspath(__file__))))

from app.core.logging_config import get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
import app.models  # noqa: E402,F401
from app.models.group import Group  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.setup import Setup  # noqa: E402
from app.core.constants import SetupStatus  # noqa: E402

logger = get_logger(__name__)

_SAMPLE_PRODUCTS = ["Networking Platform", "Storage Platform", "Compute Platform"]
_SAMPLE_GROUPS = ["Networking Lab Team", "Storage Lab Team", "Compute Lab Team"]
_SAMPLE_SETUPS = [
    {
        "product_name": "Networking Platform",
        "group_name": "Networking Lab Team",
        "ip_address": "10.10.1.11",
        "hostname": "net-lab-01.example.local",
        "location": "Rack A1, Bay 3",
    },
    {
        "product_name": "Storage Platform",
        "group_name": "Storage Lab Team",
        "ip_address": "10.10.2.11",
        "hostname": "storage-lab-01.example.local",
        "location": "Rack B2, Bay 1",
    },
]


def main() -> None:
    """Seed sample Products, Groups, and Setups if they do not already exist."""
    db = SessionLocal()
    try:
        product_by_name = {}
        for name in _SAMPLE_PRODUCTS:
            product = db.query(Product).filter(Product.name == name).first()
            if product is None:
                product = Product(name=name, description="Sample product: {0}".format(name))
                db.add(product)
                db.flush()
                logger.info("Seeded product '{0}'.".format(name))
            product_by_name[name] = product

        group_by_name = {}
        for name in _SAMPLE_GROUPS:
            group = db.query(Group).filter(Group.name == name).first()
            if group is None:
                group = Group(name=name, description="Sample group: {0}".format(name))
                db.add(group)
                db.flush()
                logger.info("Seeded group '{0}'.".format(name))
            group_by_name[name] = group

        for setup_data in _SAMPLE_SETUPS:
            existing = db.query(Setup).filter(Setup.hostname == setup_data["hostname"]).first()
            if existing is not None:
                continue
            setup = Setup(
                product_id=product_by_name[setup_data["product_name"]].id,
                group_id=group_by_name[setup_data["group_name"]].id,
                ip_address=setup_data["ip_address"],
                hostname=setup_data["hostname"],
                location=setup_data["location"],
                status=SetupStatus.AVAILABLE,
            )
            db.add(setup)
            logger.info("Seeded setup '{0}'.".format(setup_data["hostname"]))

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
