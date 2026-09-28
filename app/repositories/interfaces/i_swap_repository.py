"""Repository interface (Protocol) for the SwapRequest aggregate. The multi-node swap-mapping methods (list_by_batch_id/create_many) were removed in Phase 3 per business rule 6; historical mapping-era rows remain queryable via list()/get_by_id() and SwapResponse.batch_id."""
from typing import List, Optional, Protocol, Tuple

from app.models.swap_request import SwapRequest
from app.schemas.swap_request import SwapFilter


class ISwapRepository(Protocol):
    """Persistence contract for SwapRequest entities."""

    def get_by_id(self, swap_id: int) -> Optional[SwapRequest]:
        ...

    def list(self, filters: SwapFilter, page: int, page_size: int) -> Tuple[List[SwapRequest], int]:
        ...

    def get_pending_by_reservation_id(self, reservation_id: int) -> Optional[SwapRequest]:
        ...

    def create(self, swap_request: SwapRequest) -> SwapRequest:
        ...

    def update(self, swap_request: SwapRequest) -> SwapRequest:
        ...
