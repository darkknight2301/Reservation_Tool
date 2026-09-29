"""Repository interface (Protocol) for the BorrowRequest aggregate and its SetupAccessGrant."""
from datetime import datetime
from typing import List, Optional, Protocol, Tuple

from app.models.borrow_request import BorrowRequest
from app.models.setup_access_grant import SetupAccessGrant
from app.schemas.borrow_request import BorrowFilter


class IBorrowRepository(Protocol):
    """Persistence contract for Borrow requests and the temporary access grants they create."""

    def get_by_id(self, borrow_id: int) -> Optional[BorrowRequest]:
        ...

    def list(self, filters: BorrowFilter, page: int, page_size: int) -> Tuple[List[BorrowRequest], int]:
        ...

    def get_open_for_setup(self, setup_id: int) -> Optional[BorrowRequest]:
        """A PENDING or COMPLETED (currently borrowed) request on this setup, if any."""
        ...

    def list_stale_pending(self, now: datetime) -> List[BorrowRequest]:
        ...

    def create(self, borrow: BorrowRequest) -> BorrowRequest:
        ...

    def update(self, borrow: BorrowRequest) -> BorrowRequest:
        ...

    def create_grant(self, grant: SetupAccessGrant) -> SetupAccessGrant:
        ...

    def get_grant_for_borrow(self, borrow_id: int) -> Optional[SetupAccessGrant]:
        ...

    def get_active_grant_for_setup(self, setup_id: int) -> Optional[SetupAccessGrant]:
        ...

    def update_grant(self, grant: SetupAccessGrant) -> SetupAccessGrant:
        ...
