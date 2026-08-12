"""Add user_groups many-to-many table (multi-group user membership), backfilled from users.group_id.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-12 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_groups",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), primary_key=True),
    )

    # Every user who already has a primary group keeps that membership when
    # this feature turns on -- multi-group support is additive, not a reset.
    op.execute(
        "INSERT INTO user_groups (user_id, group_id) "
        "SELECT id, group_id FROM users WHERE group_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table("user_groups")
