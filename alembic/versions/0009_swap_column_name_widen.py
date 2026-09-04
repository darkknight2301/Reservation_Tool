"""Widen swap_requests.column_name from 100 -> 500 chars (multi-column swap selection stores a
comma-separated list of column names in this same field).

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-04 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.alter_column(
            "column_name",
            existing_type=sa.String(length=100),
            type_=sa.String(length=500),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.alter_column(
            "column_name",
            existing_type=sa.String(length=500),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
