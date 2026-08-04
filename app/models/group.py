"""
Group ORM model.

A Group represents an organizational team (e.g. "Networking Lab Team") that
users belong to and that setups can be assigned to for ownership/maintenance
purposes. Groups are independent of Products: a Product classifies *what*
a setup is (a product line), a Group classifies *who* maintains it.
"""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Group(Base):
    """A team/organizational unit that owns users and setups."""

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="group")
    setups = relationship("Setup", back_populates="group")

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<Group id={0} name={1}>".format(self.id, self.name)
