"""ExportLog ORM model. Records every Excel export performed by a user."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExportLog(Base):
    """A permanent record that a given user exported a given dataset."""

    __tablename__ = "export_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    export_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    filters = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<ExportLog id={0} export_type={1} rows={2}>".format(self.id, self.export_type, self.row_count)
