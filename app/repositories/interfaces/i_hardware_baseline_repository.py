"""Repository interface (Protocol) for ORIGINAL/BASELINE hardware state and CURRENT custom values."""
from typing import Dict, Iterable, Optional, Protocol

from app.models.setup import Setup
from app.models.setup_hardware_baseline import SetupHardwareBaseline


class IHardwareBaselineRepository(Protocol):
    """Persistence contract for fixed-field and custom-column baselines."""

    def get_fixed_baselines(self, setup_ids: Iterable[int]) -> Dict[int, SetupHardwareBaseline]:
        ...

    def ensure_fixed_baseline(self, setup: Setup) -> None:
        ...

    def get_custom_baseline_map(self, setup_ids: Iterable[int]) -> Dict[int, Dict[int, Optional[str]]]:
        ...

    def get_custom_current_map(self, setup_ids: Iterable[int]) -> Dict[int, Dict[int, Optional[str]]]:
        ...

    def get_column_names(self, column_ids: Iterable[int]) -> Dict[int, str]:
        ...

    def ensure_custom_baseline(self, setup_id: int, template_column_id: int, value: Optional[str]) -> None:
        ...
