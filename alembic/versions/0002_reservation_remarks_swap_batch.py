"""Rename reservations.purpose to remarks (Text) and add swap_requests.batch_id.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.alter_column(
            "purpose",
            new_column_name="remarks",
            existing_type=sa.String(length=500),
            type_=sa.Text(),
            existing_nullable=True,
        )

    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.add_column(sa.Column("batch_id", sa.String(length=36), nullable=True))
    op.create_index("ix_swap_requests_batch_id", "swap_requests", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_swap_requests_batch_id", table_name="swap_requests")
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.drop_column("batch_id")

    with op.batch_alter_table("reservations") as batch_op:
        batch_op.alter_column(
            "remarks",
            new_column_name="purpose",
            existing_type=sa.Text(),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
