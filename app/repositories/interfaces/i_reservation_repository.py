"""Repository interface (Protocol) for the Reservation aggregate."""
from datetime import datetime
from typing import List, Optional, Protocol, Tuple

from app.models.reservation import Reservation
from app.schemas.reservation import ReservationFilter


class IReservationRepository(Protocol):
    """Persistence contract for Reservation entities."""

    def get_by_id(self, reservation_id: int) -> Optional[Reservation]:
        ...

    def get_by_id_for_update(self, reservation_id: int) -> Optional[Reservation]:
        ...

    def list(self, filters: ReservationFilter, page: int, page_size: int) -> Tuple[List[Reservation], int]:
        ...

    def list_all(self, filters: ReservationFilter) -> List[Reservation]:
        ...

    def find_overlapping(
        self, setup_id: int, reserved_from: datetime, reserved_until: datetime, exclude_reservation_id: Optional[int] = None
    ) -> List[Reservation]:
        ...

    def create(self, reservation: Reservation) -> Reservation:
        ...

    def update(self, reservation: Reservation) -> Reservation:
        ...

    def list_expired_active(self, as_of: datetime) -> List[Reservation]:
        ...
