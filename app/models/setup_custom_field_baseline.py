"""
SetupCustomFieldBaseline ORM model.

The ORIGINAL/BASELINE value of one custom (product-template) column for one
Setup -- the counterpart of ``SetupHardwareBaseline`` for the admin-defined
columns that live in ``setup_custom_field_values`` (EAV) instead of as real
columns on ``setups``.

Stored as (setup, template column, value) rows so a product can gain a new
custom column without any schema change, exactly like the current values.
A row is captured once -- when the setup's first value for that column is
written (see ``app.models.baseline_capture``), or just before a Swap first
changes it (``HardwareStateService.ensure_custom_baseline``) -- and is never
updated afterwards. ``setup_custom_field_values.value`` remains the
CURRENT/EFFECTIVE value.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SetupCustomFieldBaseline(Base):
    """The immutable original value of one custom template column for one Setup."""

    __tablename__ = "setup_custom_field_baselines"
    __table_args__ = (
        UniqueConstraint("setup_id", "template_column_id", name="uq_custom_baseline_setup_column"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    template_column_id = Column(Integer, ForeignKey("product_template_columns.id"), nullable=False, index=True)

    value = Column(Text, nullable=True)
    captured_at = Column(DateTime, nullable=False, server_default=func.now())

    setup = relationship("Setup", foreign_keys=[setup_id])
    template_column = relationship("ProductTemplateColumn")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SetupCustomFieldBaseline setup_id={0} template_column_id={1}>".format(
            self.setup_id, self.template_column_id
        )
