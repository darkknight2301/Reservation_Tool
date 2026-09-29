"""SQLAlchemy implementation of the Borrow repository."""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.constants import BorrowStatus
from app.models.borrow_request import BorrowRequest
from app.models.setup_access_grant import SetupAccessGrant
from app.schemas.borrow_request import BorrowFilter
from app.utils.pagination import paginate_query


class BorrowRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IBorrowRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, borrow_id: int) -> Optional[BorrowRequest]:
        return self._db.query(BorrowRequest).filter(BorrowRequest.id == borrow_id).first()

    def list(self, filters: BorrowFilter, page: int, page_size: int) -> Tuple[List[BorrowRequest], int]:
        query = self._db.query(BorrowRequest)
        if filters.status:
            query = query.filter(BorrowRequest.status == filters.status)
        if filters.requester_id is not None:
            query = query.filter(BorrowRequest.requester_id == filters.requester_id)
        if filters.setup_id is not None:
            query = query.filter(BorrowRequest.setup_id == filters.setup_id)
        if filters.group_id is not None:
            query = query.filter(
                or_(BorrowRequest.source_group_id == filters.group_id, BorrowRequest.target_group_id == filters.group_id)
            )
        query = query.order_by(BorrowRequest.created_at.desc(), BorrowRequest.id.desc())
        return paginate_query(query, page, page_size)

    def get_open_for_setup(self, setup_id: int) -> Optional[BorrowRequest]:
        return (
            self._db.query(BorrowRequest)
            .filter(
                BorrowRequest.setup_id == setup_id,
                BorrowRequest.status.in_([BorrowStatus.PENDING, BorrowStatus.COMPLETED]),
            )
            .first()
        )

    def list_stale_pending(self, now: datetime) -> List[BorrowRequest]:
        return (
            self._db.query(BorrowRequest)
            .filter(
                BorrowRequest.status == BorrowStatus.PENDING,
                BorrowRequest.end_time.isnot(None),
                BorrowRequest.end_time < now,
            )
            .all()
        )

    def create(self, borrow: BorrowRequest) -> BorrowRequest:
        self._db.add(borrow)
        self._db.flush()
        self._db.refresh(borrow)
        return borrow

    def update(self, borrow: BorrowRequest) -> BorrowRequest:
        self._db.add(borrow)
        self._db.flush()
        self._db.refresh(borrow)
        return borrow

    def create_grant(self, grant: SetupAccessGrant) -> SetupAccessGrant:
        self._db.add(grant)
        self._db.flush()
        self._db.refresh(grant)
        return grant

    def get_grant_for_borrow(self, borrow_id: int) -> Optional[SetupAccessGrant]:
        return self._db.query(SetupAccessGrant).filter(SetupAccessGrant.borrow_request_id == borrow_id).first()

    def get_active_grant_for_setup(self, setup_id: int) -> Optional[SetupAccessGrant]:
        return (
            self._db.query(SetupAccessGrant)
            .filter(SetupAccessGrant.setup_id == setup_id, SetupAccessGrant.is_active.is_(True))
            .first()
        )

    def update_grant(self, grant: SetupAccessGrant) -> SetupAccessGrant:
        self._db.add(grant)
        self._db.flush()
        self._db.refresh(grant)
        return grant
