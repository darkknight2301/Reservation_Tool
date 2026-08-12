"""
SetupCustomFieldValue ORM model.

Stores the value of one custom (product-specific) template column for one
Setup, keyed by ``template_column_id``. Values are always persisted as text
(``value``); type-aware parsing/validation happens in the service layer
against the owning ``ProductTemplateColumn.data_type``. This EAV-style
design is what lets a product gain a new custom column without any
database schema migration -- a new column only ever means a new
``ProductTemplateColumn`` row, never a new SQL column on ``setups``.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SetupCustomFieldValue(Base):
    """The value of one custom template column for one Setup."""

    __tablename__ = "setup_custom_field_values"
    __table_args__ = (
        UniqueConstraint("setup_id", "template_column_id", name="uq_custom_value_setup_column"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    template_column_id = Column(Integer, ForeignKey("product_template_columns.id"), nullable=False, index=True)

    value = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    setup = relationship("Setup", back_populates="custom_field_values")
    template_column = relationship("ProductTemplateColumn")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SetupCustomFieldValue setup_id={0} template_column_id={1}>".format(
            self.setup_id, self.template_column_id
        )
