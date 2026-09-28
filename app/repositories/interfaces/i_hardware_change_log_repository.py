"""Repository interface (Protocol) for the HardwareChangeLog aggregate."""
from typing import List, Protocol

from app.models.hardware_change_log import HardwareChangeLog


class IHardwareChangeLogRepository(Protocol):
    """Persistence contract for the append-only per-field hardware change ledger."""

    def create_many(self, logs: List[HardwareChangeLog]) -> List[HardwareChangeLog]:
        ...

    def list_for_setup(self, setup_id: int) -> List[HardwareChangeLog]:
        """Every change log row for a setup, oldest first -- the full per-field history."""
        ...
