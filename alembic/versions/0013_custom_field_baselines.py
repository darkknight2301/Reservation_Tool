"""Original/Baseline storage for custom (template) columns, plus a backfill
for any Setup that still lacks a fixed-field baseline row.

* ``setup_custom_field_baselines``: (setup, template column) -> original
  value. Backfilled from the current ``setup_custom_field_values`` rows, so
  the baseline of every value that exists today is its value at migration
  time (the earliest state this database can still prove).
* ``setup_hardware_baseline`` backfill: migration 0010 snapshotted the
  setups that existed then, but no application code path created baselines
  for setups added afterwards. This inserts a baseline (from current
  values) for every setup that still has none. From now on the
  ``after_insert`` hooks in ``app.models.baseline_capture`` capture both
  kinds of baseline automatically.

Purely additive; no existing row is modified or deleted.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-29 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "setup_custom_field_baselines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column(
            "template_column_id", sa.Integer(), sa.ForeignKey("product_template_columns.id"), nullable=False
        ),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("setup_id", "template_column_id", name="uq_custom_baseline_setup_column"),
    )
    op.create_index("ix_setup_custom_field_baselines_setup_id", "setup_custom_field_baselines", ["setup_id"])
    op.create_index(
        "ix_setup_custom_field_baselines_template_column_id", "setup_custom_field_baselines", ["template_column_id"]
    )

    op.execute(
        "INSERT INTO setup_custom_field_baselines (setup_id, template_column_id, value) "
        "SELECT setup_id, template_column_id, value FROM setup_custom_field_values"
    )

    op.execute(
        "INSERT INTO setup_hardware_baseline "
        "(setup_id, ssd, hdd, hardware_info, capacity, form_factor, adapter, aardvark, quarch, apc, remote_server) "
        "SELECT id, ssd, hdd, hardware_info, capacity, form_factor, adapter, aardvark, quarch, apc, remote_server "
        "FROM setups WHERE id NOT IN (SELECT setup_id FROM setup_hardware_baseline)"
    )


def downgrade() -> None:
    # Only the new table is dropped. Baseline rows added to setup_hardware_baseline
    # by the backfill above are kept (harmless, and 0010's downgrade drops that table).
    op.drop_index("ix_setup_custom_field_baselines_template_column_id", table_name="setup_custom_field_baselines")
    op.drop_index("ix_setup_custom_field_baselines_setup_id", table_name="setup_custom_field_baselines")
    op.drop_table("setup_custom_field_baselines")
