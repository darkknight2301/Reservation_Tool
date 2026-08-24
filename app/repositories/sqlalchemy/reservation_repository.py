"""SQLAlchemy implementation of the Reservation repository."""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Query, Session

from app.core.constants import ReservationStatus
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationFilter
from app.utils.pagination import paginate_query


class ReservationRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IReservationRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, reservation_id: int) -> Optional[Reservation]:
        return self._db.query(Reservation).filter(Reservation.id == reservation_id).first()

    def get_by_id_for_update(self, reservation_id: int) -> Optional[Reservation]:
        """
        Fetch a Reservation with a row lock where the backing dialect
        supports it (PostgreSQL honors ``with_for_update``; SQLite ignores
        it but serializes writers at the database-file level instead, which
        is sufficient given SQLite's single-writer model).
        """
        return (
            self._db.query(Reservation)
            .filter(Reservation.id == reservation_id)
            .with_for_update()
            .first()
        )

    def _build_filtered_query(self, filters: ReservationFilter) -> "Query[Reservation]":
        query = self._db.query(Reservation)
        if filters.user_id is not None:
            query = query.filter(Reservation.user_id == filters.user_id)
        if filters.setup_id is not None:
            query = query.filter(Reservation.setup_id == filters.setup_id)
        if filters.status:
            query = query.filter(Reservation.status == filters.status)
        if filters.reserved_from_after is not None:
            query = query.filter(Reservation.reserved_from >= filters.reserved_from_after)
        if filters.reserved_until_before is not None:
            query = query.filter(Reservation.reserved_until <= filters.reserved_until_before)
        return query

    def list(self, filters: ReservationFilter, page: int, page_size: int) -> Tuple[List[Reservation], int]:
        query = self._build_filtered_query(filters).order_by(Reservation.reserved_from.desc())
        return paginate_query(query, page, page_size)

    def list_all(self, filters: ReservationFilter) -> List[Reservation]:
        return self._build_filtered_query(filters).order_by(Reservation.reserved_from.desc()).all()

    def find_overlapping(
        self,
        setup_id: int,
        reserved_from: datetime,
        reserved_until: datetime,
        exclude_reservation_id: Optional[int] = None,
    ) -> List[Reservation]:
        """
        Standard half-open interval overlap check: two windows [a1, a2) and
        [b1, b2) overlap unless one ends before or when the other starts.
        Only ``ACTIVE`` reservations are considered "currently occupying"
        the setup.
        """
        query = self._db.query(Reservation).filter(
            Reservation.setup_id == setup_id,
            Reservation.status == ReservationStatus.ACTIVE,
            and_(
                Reservation.reserved_from < reserved_until,
                Reservation.reserved_until > reserved_from,
            ),
        )
        if exclude_reservation_id is not None:
            query = query.filter(Reservation.id != exclude_reservation_id)
        return query.all()

    def create(self, reservation: Reservation) -> Reservation:
        self._db.add(reservation)
        self._db.flush()
        self._db.refresh(reservation)
        return reservation

    def update(self, reservation: Reservation) -> Reservation:
        self._db.add(reservation)
        self._db.flush()
        self._db.refresh(reservation)
        return reservation

    def list_expired_active(self, as_of: datetime) -> List[Reservation]:
        return (
            self._db.query(Reservation)
            .filter(Reservation.status == ReservationStatus.ACTIVE, Reservation.reserved_until <= as_of)
            .all()
        )

    def get_active_by_setup_id(self, setup_id: int) -> Optional[Reservation]:
        return (
            self._db.query(Reservation)
            .filter(Reservation.setup_id == setup_id, Reservation.status == ReservationStatus.ACTIVE)
            .first()
        )
