"""
ProductTemplateColumn ORM model.

Represents one *custom* (product-specific) column defined on a Product's
table template. The eight mandatory columns (IP, User, Owner, Reservation,
Remark, Location, Group, Product) are NOT rows in this table -- they are
fixed, built-in columns every product always has (see
``app.core.constants.MANDATORY_TEMPLATE_COLUMNS``) and are never stored or
editable here. Only additional, product-specific columns live in this
table, which is why adding a new custom column to a product never requires
a database schema migration: it is a new row, not a new SQL column.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProductTemplateColumn(Base):
    """A single custom column defined on a Product's dynamic template."""

    __tablename__ = "product_template_columns"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_template_column_product_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    # ``name`` is the stable, machine-usable key (used as the Excel header and
    # as the key of the custom-field-value map). ``label`` is what's shown in
    # the UI; it defaults to ``name`` when not explicitly customized.
    name = Column(String(100), nullable=False)
    label = Column(String(150), nullable=False)

    # One of ColumnDataType.ALL (String, Integer, Float, Boolean, Date, DateTime, Dropdown).
    data_type = Column(String(20), nullable=False)

    required = Column(Boolean, nullable=False, default=False)
    default_value = Column(String(500), nullable=True)

    # JSON-encoded list of allowed values, only meaningful when data_type == DROPDOWN.
    allowed_values = Column(Text, nullable=True)

    order_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="template_columns")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<ProductTemplateColumn id={0} product_id={1} name={2}>".format(
            self.id, self.product_id, self.name
        )
