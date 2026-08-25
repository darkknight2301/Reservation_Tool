"""Add swap_requests.previous_current_value / previous_requested_value (pre-swap values, for restoration).

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-26 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("swap_requests", sa.Column("previous_current_value", sa.String(length=500), nullable=True))
    op.add_column("swap_requests", sa.Column("previous_requested_value", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("swap_requests", "previous_requested_value")
    op.drop_column("swap_requests", "previous_current_value")
