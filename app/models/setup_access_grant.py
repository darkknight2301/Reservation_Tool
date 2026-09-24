"""
SetupAccessGrant ORM model.

The explicit "temporary borrowed access" concept called for by the business
rule "Do not use a single 'owner' field to represent all of these concepts
... Design an explicit access model if required." An approved
``BorrowRequest`` creates exactly one active grant; returning the borrow
closes it (``is_active = False``, ``returned_at`` set) rather than deleting
it, so borrow history stays queryable.

``Setup.group_id`` (the ORIGINAL owning group) is never overwritten by a
Borrow. "Effective access holder" for a Setup is computed as: the active
grant's ``granted_to_group_id`` if one exists, else ``Setup.group_id`` --
this is a read-time derivation (Phase 4 service logic), not a column, so
there is exactly one place a grant can ever disagree with reality: this
table.

At most one active grant per setup is expected (enforced in the service
layer when Borrow is implemented in Phase 4, not as a DB constraint --
mirrors how reservation-overlap is enforced in ``ReservationService`` rather
than the schema, for the same SQLite/PostgreSQL portability reason).
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class SetupAccessGrant(Base):
    """A temporary, borrow-derived effective access holder for one Setup."""

    __tablename__ = "setup_access_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, index=True)
    borrow_request_id = Column(Integer, ForeignKey("borrow_requests.id"), nullable=False, unique=True, index=True)

    source_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    granted_to_group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    granted_at = Column(DateTime, nullable=False, server_default=func.now())
    returned_at = Column(DateTime, nullable=True)

    setup = relationship("Setup", foreign_keys=[setup_id])
    borrow_request = relationship("BorrowRequest", foreign_keys=[borrow_request_id])
    source_group = relationship("Group", foreign_keys=[source_group_id])
    granted_to_group = relationship("Group", foreign_keys=[granted_to_group_id])

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return "<SetupAccessGrant setup_id={0} granted_to_group_id={1} active={2}>".format(
            self.setup_id, self.granted_to_group_id, self.is_active
        )
