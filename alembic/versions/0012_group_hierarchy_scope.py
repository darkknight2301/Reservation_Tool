"""Add ``scope`` to group_hierarchy_edges (SWAP / BORROW / BOTH), so the
same hierarchy table can express edges that apply to only one approval
domain when an org's Swap and Borrow reporting lines genuinely differ for
a relationship -- see app.models.group_hierarchy_edge and
app.core.constants.ApprovalHierarchyScope for the full rationale (found
necessary while validating the Borrow routing example against the
business rules: Group D is a child of both A, relevant only to Swap, and
B, relevant only to Borrow). Additive: the table is new as of migration
0010 and not yet written to by any shipped code path, so there is no
existing data to backfill.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-27 00:10:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("group_hierarchy_edges") as batch_op:
        batch_op.drop_constraint("uq_group_hierarchy_edge", type_="unique")
        batch_op.add_column(
            sa.Column("scope", sa.String(length=10), nullable=False, server_default="BOTH")
        )
        batch_op.create_check_constraint(
            "ck_group_hierarchy_edges_scope", "scope IN ('SWAP', 'BORROW', 'BOTH')"
        )
        batch_op.create_unique_constraint(
            "uq_group_hierarchy_edge", ["parent_group_id", "child_group_id", "scope"]
        )


def downgrade() -> None:
    with op.batch_alter_table("group_hierarchy_edges") as batch_op:
        batch_op.drop_constraint("uq_group_hierarchy_edge", type_="unique")
        batch_op.drop_constraint("ck_group_hierarchy_edges_scope", type_="check")
        batch_op.drop_column("scope")
        batch_op.create_unique_constraint(
            "uq_group_hierarchy_edge", ["parent_group_id", "child_group_id"]
        )
