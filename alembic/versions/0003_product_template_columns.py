"""Add product_template_columns and setup_custom_field_values tables (Dynamic Product Template feature).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-12 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_template_columns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value", sa.String(length=500), nullable=True),
        sa.Column("allowed_values", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "name", name="uq_template_column_product_name"),
    )
    op.create_index("ix_product_template_columns_product_id", "product_template_columns", ["product_id"])

    op.create_table(
        "setup_custom_field_values",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column("template_column_id", sa.Integer(), sa.ForeignKey("product_template_columns.id"), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("setup_id", "template_column_id", name="uq_custom_value_setup_column"),
    )
    op.create_index("ix_setup_custom_field_values_setup_id", "setup_custom_field_values", ["setup_id"])
    op.create_index(
        "ix_setup_custom_field_values_template_column_id", "setup_custom_field_values", ["template_column_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_setup_custom_field_values_template_column_id", table_name="setup_custom_field_values")
    op.drop_index("ix_setup_custom_field_values_setup_id", table_name="setup_custom_field_values")
    op.drop_table("setup_custom_field_values")

    op.drop_index("ix_product_template_columns_product_id", table_name="product_template_columns")
    op.drop_table("product_template_columns")
