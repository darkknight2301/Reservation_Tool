"""SQLAlchemy implementation of the Setup repository."""
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.models.setup import Setup
from app.schemas.setup import SetupFilter
from app.utils.pagination import paginate_query


class SetupRepository:
    """Concrete, SQLAlchemy-backed implementation of ``ISetupRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, setup_id: int) -> Optional[Setup]:
        return self._db.query(Setup).filter(Setup.id == setup_id).first()

    def get_by_ip_or_hostname(self, ip_address: str, hostname: str) -> Optional[Setup]:
        return (
            self._db.query(Setup)
            .filter(or_(Setup.ip_address == ip_address, Setup.hostname == hostname))
            .first()
        )

    def _build_filtered_query(self, filters: SetupFilter) -> "Query[Setup]":
        query = self._db.query(Setup)
        if filters.product_id is not None:
            query = query.filter(Setup.product_id == filters.product_id)
        if filters.group_id is not None:
            query = query.filter(Setup.group_id == filters.group_id)
        if filters.status:
            query = query.filter(Setup.status == filters.status)
        if filters.location:
            query = query.filter(Setup.location.ilike("%{0}%".format(filters.location)))
        if filters.owner_id is not None:
            query = query.filter(Setup.owner_id == filters.owner_id)
        if filters.search:
            like_pattern = "%{0}%".format(filters.search)
            query = query.filter(
                or_(
                    Setup.hostname.ilike(like_pattern),
                    Setup.ip_address.ilike(like_pattern),
                    Setup.hardware_info.ilike(like_pattern),
                )
            )
        return query

    def list(self, filters: SetupFilter, page: int, page_size: int) -> Tuple[List[Setup], int]:
        query = self._build_filtered_query(filters).order_by(Setup.created_at.desc())
        return paginate_query(query, page, page_size)

    def list_all(self, filters: SetupFilter) -> List[Setup]:
        return self._build_filtered_query(filters).order_by(Setup.created_at.desc()).all()

    def create(self, setup: Setup) -> Setup:
        self._db.add(setup)
        self._db.flush()
        self._db.refresh(setup)
        return setup

    def update(self, setup: Setup) -> Setup:
        self._db.add(setup)
        self._db.flush()
        self._db.refresh(setup)
        return setup

    def update_status(self, setup_id: int, status: str) -> None:
        setup = self.get_by_id(setup_id)
        if setup is not None:
            setup.status = status
            self._db.add(setup)
            self._db.flush()

    def delete(self, setup_id: int) -> None:
        setup = self.get_by_id(setup_id)
        if setup is not None:
            self._db.delete(setup)
            self._db.flush()

    def get_by_product_id(self, product_id: int) -> List[Setup]:
        return self._db.query(Setup).filter(Setup.product_id == product_id).all()
