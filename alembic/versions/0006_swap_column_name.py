"""Add swap_requests.column_name (swap now exchanges one field's value between two self-reserved setups).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-20 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("swap_requests", sa.Column("column_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("swap_requests", "column_name")
