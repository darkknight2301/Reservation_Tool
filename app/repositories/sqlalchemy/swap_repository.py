"""SQLAlchemy implementation of the SwapRequest repository."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.constants import SwapStatus
from app.models.swap_request import SwapRequest
from app.schemas.swap_request import SwapFilter
from app.utils.pagination import paginate_query


class SwapRepository:
    """Concrete, SQLAlchemy-backed implementation of ``ISwapRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, swap_id: int) -> Optional[SwapRequest]:
        return self._db.query(SwapRequest).filter(SwapRequest.id == swap_id).first()

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        query = self._db.query(SwapRequest)
        if filters.status:
            query = query.filter(SwapRequest.status == filters.status)
        if filters.requester_id is not None:
            query = query.filter(SwapRequest.requester_id == filters.requester_id)
        query = query.order_by(SwapRequest.created_at.desc())
        return paginate_query(query, page, page_size)

    def list_by_batch_id(self, batch_id: str) -> List[SwapRequest]:
        return self._db.query(SwapRequest).filter(SwapRequest.batch_id == batch_id).all()

    def get_pending_by_reservation_id(self, reservation_id: int) -> Optional[SwapRequest]:
        return (
            self._db.query(SwapRequest)
            .filter(SwapRequest.reservation_id == reservation_id, SwapRequest.status == SwapStatus.PENDING)
            .first()
        )

    def create(self, swap_request: SwapRequest) -> SwapRequest:
        self._db.add(swap_request)
        self._db.flush()
        self._db.refresh(swap_request)
        return swap_request

    def create_many(self, swap_requests: List[SwapRequest]) -> List[SwapRequest]:
        self._db.add_all(swap_requests)
        self._db.flush()
        for swap_request in swap_requests:
            self._db.refresh(swap_request)
        return swap_requests

    def update(self, swap_request: SwapRequest) -> SwapRequest:
        self._db.add(swap_request)
        self._db.flush()
        self._db.refresh(swap_request)
        return swap_request
