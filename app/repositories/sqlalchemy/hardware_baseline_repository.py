"""SQLAlchemy implementation of the hardware-baseline repository."""
from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.hardware_change_log import HardwareChangeLog
from app.models.product_template_column import ProductTemplateColumn
from app.models.setup import Setup
from app.models.setup_custom_field_baseline import SetupCustomFieldBaseline
from app.models.setup_custom_field_value import SetupCustomFieldValue
from app.models.setup_hardware_baseline import BASELINE_FIELD_NAMES, SetupHardwareBaseline


class HardwareBaselineRepository:
    """Concrete, SQLAlchemy-backed implementation of ``IHardwareBaselineRepository``."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_fixed_baselines(self, setup_ids: Iterable[int]) -> Dict[int, SetupHardwareBaseline]:
        ids = list(setup_ids)
        if not ids:
            return {}
        rows = self._db.query(SetupHardwareBaseline).filter(SetupHardwareBaseline.setup_id.in_(ids)).all()
        return {row.setup_id: row for row in rows}

    def ensure_fixed_baseline(self, setup: Setup) -> None:
        """Safety net for a legacy setup with no baseline row: snapshot its *current* values (never overwrites an existing one)."""
        existing = self._db.query(SetupHardwareBaseline).filter(SetupHardwareBaseline.setup_id == setup.id).first()
        if existing is None:
            self._db.add(SetupHardwareBaseline(
                setup_id=setup.id, **{name: getattr(setup, name, None) for name in BASELINE_FIELD_NAMES}
            ))
            self._db.flush()

    def get_custom_baseline_map(self, setup_ids: Iterable[int]) -> Dict[int, Dict[int, Optional[str]]]:
        ids = list(setup_ids)
        result: Dict[int, Dict[int, Optional[str]]] = {}
        if not ids:
            return result
        for row in self._db.query(SetupCustomFieldBaseline).filter(SetupCustomFieldBaseline.setup_id.in_(ids)).all():
            result.setdefault(row.setup_id, {})[row.template_column_id] = row.value
        return result

    def get_custom_current_map(self, setup_ids: Iterable[int]) -> Dict[int, Dict[int, Optional[str]]]:
        ids = list(setup_ids)
        result: Dict[int, Dict[int, Optional[str]]] = {}
        if not ids:
            return result
        for row in self._db.query(SetupCustomFieldValue).filter(SetupCustomFieldValue.setup_id.in_(ids)).all():
            result.setdefault(row.setup_id, {})[row.template_column_id] = row.value
        return result

    def get_column_names(self, column_ids: Iterable[int]) -> Dict[int, str]:
        ids = list(set(column_ids))
        if not ids:
            return {}
        rows = self._db.query(ProductTemplateColumn).filter(ProductTemplateColumn.id.in_(ids)).all()
        return {row.id: row.name for row in rows}

    def ensure_custom_baseline(self, setup_id: int, template_column_id: int, value: Optional[str]) -> None:
        """Record ``value`` as the original for this setup/column unless a baseline already exists (never overwrites)."""
        existing = (
            self._db.query(SetupCustomFieldBaseline)
            .filter(
                SetupCustomFieldBaseline.setup_id == setup_id,
                SetupCustomFieldBaseline.template_column_id == template_column_id,
            )
            .first()
        )
        if existing is None:
            self._db.add(SetupCustomFieldBaseline(setup_id=setup_id, template_column_id=template_column_id, value=value))
            self._db.flush()

    def set_fixed_baseline_fields(self, setup: Setup, field_names: Iterable[str]) -> None:
        """Overwrite the given fixed-field baselines with the setup's CURRENT values (creating the baseline row if missing)."""
        self.ensure_fixed_baseline(setup)
        baseline = self._db.query(SetupHardwareBaseline).filter(SetupHardwareBaseline.setup_id == setup.id).one()
        for name in field_names:
            if name in BASELINE_FIELD_NAMES:
                setattr(baseline, name, getattr(setup, name, None))
        self._db.add(baseline)
        self._db.flush()

    def set_custom_baseline(self, setup_id: int, template_column_id: int, value: Optional[str]) -> None:
        """Upsert a custom-column baseline (used only by an explicit admin re-baseline)."""
        existing = (
            self._db.query(SetupCustomFieldBaseline)
            .filter(
                SetupCustomFieldBaseline.setup_id == setup_id,
                SetupCustomFieldBaseline.template_column_id == template_column_id,
            )
            .first()
        )
        if existing is None:
            self._db.add(SetupCustomFieldBaseline(setup_id=setup_id, template_column_id=template_column_id, value=value))
        else:
            existing.value = value
            self._db.add(existing)
        self._db.flush()

    def list_changes(self, setup_id: int, limit: int = 50) -> list:
        """Newest-first hardware change ledger rows (Swap/Borrow/Edit history) for one setup."""
        return (
            self._db.query(HardwareChangeLog)
            .filter(HardwareChangeLog.setup_id == setup_id)
            .order_by(HardwareChangeLog.created_at.desc(), HardwareChangeLog.id.desc())
            .limit(limit)
            .all()
        )
