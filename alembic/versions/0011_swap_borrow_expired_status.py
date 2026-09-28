"""Add EXPIRED to the swap_requests and borrow_requests status CHECK
constraints (gap closed during the Phase 1/2/3 re-verification pass -- see
IMPLEMENTATION_PROGRESS.md). Purely additive to the allowed value set; no
existing row's status value is touched, and no other column changes.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-27 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.drop_constraint("ck_swap_requests_status", type_="check")
        batch_op.create_check_constraint(
            "ck_swap_requests_status",
            "status IN ('PENDING','APPROVED','REJECTED','COMPLETED','CANCELLED','EXPIRED')",
        )

    with op.batch_alter_table("borrow_requests") as batch_op:
        batch_op.drop_constraint("ck_borrow_requests_status", type_="check")
        batch_op.create_check_constraint(
            "ck_borrow_requests_status",
            "status IN ('PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED', 'RETURNED', 'EXPIRED')",
        )


def downgrade() -> None:
    with op.batch_alter_table("borrow_requests") as batch_op:
        batch_op.drop_constraint("ck_borrow_requests_status", type_="check")
        batch_op.create_check_constraint(
            "ck_borrow_requests_status",
            "status IN ('PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED', 'RETURNED')",
        )

    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.drop_constraint("ck_swap_requests_status", type_="check")
        batch_op.create_check_constraint(
            "ck_swap_requests_status",
            "status IN ('PENDING','APPROVED','REJECTED','COMPLETED','CANCELLED')",
        )
