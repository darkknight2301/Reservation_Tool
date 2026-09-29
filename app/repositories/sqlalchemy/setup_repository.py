"""SQLAlchemy implementation of the Setup repository."""
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

from app.models.setup import Setup
from app.models.setup_access_grant import SetupAccessGrant
from app.models.setup_custom_field_baseline import SetupCustomFieldBaseline
from app.models.setup_hardware_baseline import SetupHardwareBaseline
from app.schemas.setup import SetupFilter
from app.utils.pagination import paginate_query


class SetupRepository:
    """Concrete, SQLAlchemy-backed implementation of ``ISetupRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, setup_id: int) -> Optional[Setup]:
        return self._db.query(Setup).filter(Setup.id == setup_id).first()

    def get_active_grants(self, setup_ids: List[int]) -> dict:
        """``{setup_id: active SetupAccessGrant}`` for the given setups (used to show who currently holds a lent-out setup)."""
        if not setup_ids:
            return {}
        rows = (
            self._db.query(SetupAccessGrant)
            .filter(SetupAccessGrant.setup_id.in_(setup_ids), SetupAccessGrant.is_active.is_(True))
            .all()
        )
        return {row.setup_id: row for row in rows}

    def get_active_grant_group_ids(self, setup_id: int) -> List[int]:
        """Group ids currently holding temporary (borrowed) access to this setup."""
        rows = (
            self._db.query(SetupAccessGrant.granted_to_group_id)
            .filter(SetupAccessGrant.setup_id == setup_id, SetupAccessGrant.is_active.is_(True))
            .all()
        )
        return [row[0] for row in rows]

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
            # EFFECTIVE group: a setup currently lent out via an active Borrow grant is
            # listed under the borrowing group instead of its (unchanged) owning group.
            any_active_grant = (
                self._db.query(SetupAccessGrant.id)
                .filter(SetupAccessGrant.setup_id == Setup.id, SetupAccessGrant.is_active.is_(True))
                .exists()
            )
            granted_to_group = (
                self._db.query(SetupAccessGrant.setup_id)
                .filter(SetupAccessGrant.granted_to_group_id == filters.group_id, SetupAccessGrant.is_active.is_(True))
            )
            query = query.filter(
                or_(and_(Setup.group_id == filters.group_id, ~any_active_grant), Setup.id.in_(granted_to_group))
            )
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
            # A setup's ORIGINAL/BASELINE rows are automatically created with it
            # (see app.models.baseline_capture) and have no meaning without it,
            # so they go with it; otherwise their FK would block deleting any setup.
            self._db.query(SetupHardwareBaseline).filter(SetupHardwareBaseline.setup_id == setup_id).delete(synchronize_session=False)
            self._db.query(SetupCustomFieldBaseline).filter(SetupCustomFieldBaseline.setup_id == setup_id).delete(synchronize_session=False)
            self._db.delete(setup)
            self._db.flush()

    def get_by_product_id(self, product_id: int) -> List[Setup]:
        return self._db.query(Setup).filter(Setup.product_id == product_id).all()
