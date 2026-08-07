"""Repository interface (Protocol) for the SwapRequest aggregate."""
from typing import List, Optional, Protocol, Tuple

from app.models.swap_request import SwapRequest
from app.schemas.swap_request import SwapFilter


class ISwapRepository(Protocol):
    """Persistence contract for SwapRequest entities."""

    def get_by_id(self, swap_id: int) -> Optional[SwapRequest]:
        ...

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        ...

    def list_by_batch_id(self, batch_id: str) -> List[SwapRequest]:
        ...

    def get_pending_by_reservation_id(self, reservation_id: int) -> Optional[SwapRequest]:
        ...

    def create(self, swap_request: SwapRequest) -> SwapRequest:
        ...

    def create_many(self, swap_requests: List[SwapRequest]) -> List[SwapRequest]:
        ...

    def update(self, swap_request: SwapRequest) -> SwapRequest:
        ...
