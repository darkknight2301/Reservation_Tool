"""SQLAlchemy implementation of the HardwareChangeLog repository."""
from typing import List

from sqlalchemy.orm import Session

from app.models.hardware_change_log import HardwareChangeLog


class HardwareChangeLogRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IHardwareChangeLogRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_many(self, logs: List[HardwareChangeLog]) -> List[HardwareChangeLog]:
        self._db.add_all(logs)
        self._db.flush()
        for log in logs:
            self._db.refresh(log)
        return logs

    def list_for_setup(self, setup_id: int) -> List[HardwareChangeLog]:
        return (
            self._db.query(HardwareChangeLog)
            .filter(HardwareChangeLog.setup_id == setup_id)
            .order_by(HardwareChangeLog.created_at.asc(), HardwareChangeLog.id.asc())
            .all()
        )
