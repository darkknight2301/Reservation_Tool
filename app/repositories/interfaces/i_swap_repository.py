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

    def create(self, swap_request: SwapRequest) -> SwapRequest:
        ...

    def update(self, swap_request: SwapRequest) -> SwapRequest:
        ...
