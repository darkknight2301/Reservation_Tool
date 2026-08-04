"""
SQLAlchemy declarative base shared by every ORM model.

Kept in its own module (rather than inside ``session.py``) purely so that
Alembic's ``env.py`` can import ``Base.metadata`` without also importing the
live engine/session machinery.
"""
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
