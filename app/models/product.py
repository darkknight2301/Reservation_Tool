"""Product ORM model. Setups are grouped under a Product."""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Product(Base):
    """A product line that reservable setups belong to."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    setups = relationship("Setup", back_populates="product")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Product id={0} name={1}>".format(self.id, self.name)
