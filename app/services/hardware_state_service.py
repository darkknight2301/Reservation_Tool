"""
Hardware state service: ORIGINAL vs CURRENT comparison.

Answers one question -- "which hardware fields of these setups differ from
their original/baseline state?" -- generically, for both kinds of field:

  * fixed hardware columns on ``setups`` (baseline: ``SetupHardwareBaseline``);
  * admin-defined custom template columns (baseline: ``SetupCustomFieldBaseline``).

The field list is never hardcoded: fixed fields come from the baseline
table's own columns (``BASELINE_FIELD_NAMES``), custom fields from whatever
baseline/current rows exist. The web layer uses the result to highlight
exactly the changed cells, so any field that changes -- now or after an
admin adds a new column -- is highlighted without touching this code.

Read-only apart from the two ``ensure_*`` helpers, which only ever create a
missing baseline (a safety net for legacy rows) and never modify one.
"""
from typing import Any, Dict, Iterable, List, Optional

from app.models.setup import Setup
from app.models.setup_hardware_baseline import BASELINE_FIELD_NAMES
from app.repositories.interfaces.i_hardware_baseline_repository import IHardwareBaselineRepository


def _normalize(value: Optional[object]) -> str:
    """None and blank compare equal; surrounding whitespace is not a change."""
    return "" if value is None else str(value).strip()


class HardwareStateService:
    """Original-vs-Current comparison and baseline safety-net helpers."""

    def __init__(self, baseline_repository: IHardwareBaselineRepository) -> None:
        self._baseline_repository = baseline_repository

    def changed_fields(self, setups: Iterable[Setup]) -> Dict[int, List[str]]:
        """
        ``{setup_id: [field_name, ...]}`` for every setup that has at least
        one field whose CURRENT value differs from its ORIGINAL value. Fixed
        fields are keyed by column name (e.g. ``ssd``), custom fields by
        their template-column ``name``. A field with no recorded baseline is
        treated as unchanged (nothing to compare against).
        """
        setups = list(setups)
        if not setups:
            return {}
        ids = [setup.id for setup in setups]

        fixed_baselines = self._baseline_repository.get_fixed_baselines(ids)
        custom_baselines = self._baseline_repository.get_custom_baseline_map(ids)
        custom_current = self._baseline_repository.get_custom_current_map(ids)

        column_ids = set()
        for mapping in list(custom_baselines.values()) + list(custom_current.values()):
            column_ids.update(mapping.keys())
        names = self._baseline_repository.get_column_names(column_ids)

        result: Dict[int, List[str]] = {}
        for setup in setups:
            changed: List[str] = []

            baseline = fixed_baselines.get(setup.id)
            if baseline is not None:
                for field_name in BASELINE_FIELD_NAMES:
                    if _normalize(getattr(setup, field_name, None)) != _normalize(getattr(baseline, field_name, None)):
                        changed.append(field_name)

            base_map = custom_baselines.get(setup.id, {})
            current_map = custom_current.get(setup.id, {})
            for column_id, original_value in base_map.items():
                if column_id not in names:
                    continue
                if _normalize(current_map.get(column_id)) != _normalize(original_value):
                    changed.append(names[column_id])

            if changed:
                result[setup.id] = changed
        return result

    def ensure_fixed_baseline(self, setup: Setup) -> None:
        """Make sure ``setup`` has an original snapshot BEFORE its current values are changed."""
        self._baseline_repository.ensure_fixed_baseline(setup)

    def ensure_custom_baseline(self, setup_id: int, template_column_id: int, current_value: Optional[str]) -> None:
        """Make sure this custom column has an original value BEFORE it is changed (``current_value`` is the pre-change value)."""
        self._baseline_repository.ensure_custom_baseline(setup_id, template_column_id, current_value)

    def rebaseline_edited_fields(
        self,
        setup: Setup,
        before_fixed: Dict[str, Any],
        custom_column_ids: Dict[str, int],
        before_custom: Dict[str, Any],
        after_custom: Dict[str, Any],
    ) -> List[str]:
        """
        Admin "Setup Edit" semantics: a value the admin actually edited
        becomes the setup's new ORIGINAL value (an edit is a correction,
        not a hardware event). Only fields whose value differs before vs.
        after the edit are re-baselined, so an unrelated field that is
        still legitimately swapped/changed keeps its highlight. Returns the
        names of the re-baselined fields.
        """
        fixed_changed = [
            name for name in BASELINE_FIELD_NAMES
            if _normalize(before_fixed.get(name)) != _normalize(getattr(setup, name, None))
        ]
        if fixed_changed:
            self._baseline_repository.set_fixed_baseline_fields(setup, fixed_changed)

        custom_changed: List[str] = []
        for name, column_id in custom_column_ids.items():
            if _normalize(before_custom.get(name)) != _normalize(after_custom.get(name)):
                self._baseline_repository.set_custom_baseline(setup.id, column_id, after_custom.get(name))
                custom_changed.append(name)
        return fixed_changed + custom_changed

    def compare(self, setup: Setup, custom_columns: Iterable[Any]) -> List[Dict[str, Any]]:
        """
        Full Original-vs-Current table for one setup: one row per fixed field
        and per custom column (``custom_columns``: objects with ``id``, ``name``,
        ``label``), each ``{field, label, original, current, changed}``.
        Generic like ``changed_fields`` -- no per-field logic.
        """
        baseline = self._baseline_repository.get_fixed_baselines([setup.id]).get(setup.id)
        rows: List[Dict[str, Any]] = []
        for name in BASELINE_FIELD_NAMES:
            current = getattr(setup, name, None)
            original = getattr(baseline, name, None) if baseline is not None else current
            rows.append({
                "field": name, "label": name.replace("_", " ").title(),
                "original": original, "current": current,
                "changed": _normalize(original) != _normalize(current),
            })
        custom_base = self._baseline_repository.get_custom_baseline_map([setup.id]).get(setup.id, {})
        custom_now = self._baseline_repository.get_custom_current_map([setup.id]).get(setup.id, {})
        for column in custom_columns:
            current = custom_now.get(column.id)
            original = custom_base.get(column.id, current)
            rows.append({
                "field": column.name, "label": column.label or column.name,
                "original": original, "current": current,
                "changed": _normalize(original) != _normalize(current),
            })
        return rows

    def history(self, setup_id: int, limit: int = 50) -> list:
        """Newest-first hardware change ledger (which request changed what, when, by whom)."""
        return self._baseline_repository.list_changes(setup_id, limit)
