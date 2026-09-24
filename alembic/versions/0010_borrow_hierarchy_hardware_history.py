"""Phase 1 data model: Borrow aggregate, data-driven approval hierarchy,
hardware Original/Baseline snapshot + per-field change ledger, and additive
Swap redesign columns (setup_id, start/end time, announcement, routed
approver emails). Entirely additive -- no existing table, column, or row is
dropped, renamed, or destructively altered. See ARCHITECTURE_ASSESSMENT.md
for the full rationale.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-24 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed hardware columns baselined/ledgered -- kept in lock-step with
# app.services.swap_service.SWAPPABLE_SETUP_FIELDS. Duplicated here (rather
# than imported) because Alembic revisions must remain runnable against
# whatever the application code looked like *at the time the revision was
# authored*, independent of later refactors to that constant.
_HARDWARE_FIELDS = (
    "ssd", "hdd", "hardware_info", "capacity", "form_factor",
    "adapter", "aardvark", "quarch", "apc", "remote_server",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Hardware ORIGINAL/BASELINE snapshot (one row per existing Setup,
    #    backfilled from its current values so "baseline" is well-defined
    #    for every setup that already exists, not just new ones).
    # ------------------------------------------------------------------
    op.create_table(
        "setup_hardware_baseline",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column("ssd", sa.String(length=100), nullable=True),
        sa.Column("hdd", sa.String(length=100), nullable=True),
        sa.Column("hardware_info", sa.String(length=500), nullable=True),
        sa.Column("capacity", sa.String(length=100), nullable=True),
        sa.Column("form_factor", sa.String(length=50), nullable=True),
        sa.Column("adapter", sa.String(length=100), nullable=True),
        sa.Column("aardvark", sa.String(length=100), nullable=True),
        sa.Column("quarch", sa.String(length=100), nullable=True),
        sa.Column("apc", sa.String(length=100), nullable=True),
        sa.Column("remote_server", sa.String(length=255), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("setup_id", name="uq_setup_hardware_baseline_setup_id"),
    )
    op.create_index("ix_setup_hardware_baseline_setup_id", "setup_hardware_baseline", ["setup_id"])

    op.execute(
        "INSERT INTO setup_hardware_baseline "
        "(setup_id, ssd, hdd, hardware_info, capacity, form_factor, adapter, aardvark, quarch, apc, remote_server) "
        "SELECT id, ssd, hdd, hardware_info, capacity, form_factor, adapter, aardvark, quarch, apc, remote_server "
        "FROM setups"
    )

    # ------------------------------------------------------------------
    # 2. Append-only per-field hardware change ledger.
    # ------------------------------------------------------------------
    op.create_table(
        "hardware_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_request_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('SWAP', 'BORROW')", name="ck_hardware_change_logs_source"),
    )
    op.create_index("ix_hardware_change_logs_setup_id", "hardware_change_logs", ["setup_id"])
    op.create_index("ix_hardware_change_logs_field_name", "hardware_change_logs", ["field_name"])
    op.create_index("ix_hardware_change_logs_source", "hardware_change_logs", ["source"])
    op.create_index("ix_hardware_change_logs_source_request_id", "hardware_change_logs", ["source_request_id"])
    op.create_index("ix_hardware_change_logs_created_at", "hardware_change_logs", ["created_at"])

    # ------------------------------------------------------------------
    # 3. Data-driven approval hierarchy (directed edges between Groups;
    #    a DAG, not a strict tree -- a child Group may have more than one
    #    parent, per the Borrow routing example in ARCHITECTURE_ASSESSMENT.md).
    # ------------------------------------------------------------------
    op.create_table(
        "group_hierarchy_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("parent_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("child_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("parent_group_id != child_group_id", name="ck_group_hierarchy_edge_no_self_loop"),
        sa.UniqueConstraint("parent_group_id", "child_group_id", name="uq_group_hierarchy_edge"),
    )
    op.create_index("ix_group_hierarchy_edges_parent_group_id", "group_hierarchy_edges", ["parent_group_id"])
    op.create_index("ix_group_hierarchy_edges_child_group_id", "group_hierarchy_edges", ["child_group_id"])

    # ------------------------------------------------------------------
    # 4. Borrow aggregate.
    # ------------------------------------------------------------------
    op.create_table(
        "borrow_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("target_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column("hardware_field_name", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("announcement_channels", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("routed_approver_emails", sa.Text(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.Column("returned_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED', 'RETURNED')",
            name="ck_borrow_requests_status",
        ),
    )
    op.create_index("ix_borrow_requests_requester_id", "borrow_requests", ["requester_id"])
    op.create_index("ix_borrow_requests_source_group_id", "borrow_requests", ["source_group_id"])
    op.create_index("ix_borrow_requests_target_group_id", "borrow_requests", ["target_group_id"])
    op.create_index("ix_borrow_requests_setup_id", "borrow_requests", ["setup_id"])
    op.create_index("ix_borrow_requests_status", "borrow_requests", ["status"])

    op.create_table(
        "setup_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=False),
        sa.Column("borrow_request_id", sa.Integer(), sa.ForeignKey("borrow_requests.id"), nullable=False),
        sa.Column("source_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("granted_to_group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("borrow_request_id", name="uq_setup_access_grant_borrow_request_id"),
    )
    op.create_index("ix_setup_access_grants_setup_id", "setup_access_grants", ["setup_id"])
    op.create_index("ix_setup_access_grants_borrow_request_id", "setup_access_grants", ["borrow_request_id"])
    op.create_index("ix_setup_access_grants_is_active", "setup_access_grants", ["is_active"])

    # ------------------------------------------------------------------
    # 5. Swap redesign: widen legacy relocation columns to nullable, add
    #    the new single-setup + reason/start/end/announcement/routing
    #    columns. SQLite requires batch mode to alter column nullability.
    # ------------------------------------------------------------------
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.alter_column("reservation_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("current_setup_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("requested_setup_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("setup_id", sa.Integer(), sa.ForeignKey("setups.id"), nullable=True))
        batch_op.add_column(sa.Column("start_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("end_time", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("announcement_channels", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("routed_approver_emails", sa.Text(), nullable=True))
    op.create_index("ix_swap_requests_setup_id", "swap_requests", ["setup_id"])


def downgrade() -> None:
    op.drop_index("ix_swap_requests_setup_id", table_name="swap_requests")
    with op.batch_alter_table("swap_requests") as batch_op:
        batch_op.drop_column("routed_approver_emails")
        batch_op.drop_column("announcement_channels")
        batch_op.drop_column("end_time")
        batch_op.drop_column("start_time")
        batch_op.drop_column("setup_id")
        batch_op.alter_column("requested_setup_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("current_setup_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("reservation_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index("ix_setup_access_grants_is_active", table_name="setup_access_grants")
    op.drop_index("ix_setup_access_grants_borrow_request_id", table_name="setup_access_grants")
    op.drop_index("ix_setup_access_grants_setup_id", table_name="setup_access_grants")
    op.drop_table("setup_access_grants")

    op.drop_index("ix_borrow_requests_status", table_name="borrow_requests")
    op.drop_index("ix_borrow_requests_setup_id", table_name="borrow_requests")
    op.drop_index("ix_borrow_requests_target_group_id", table_name="borrow_requests")
    op.drop_index("ix_borrow_requests_source_group_id", table_name="borrow_requests")
    op.drop_index("ix_borrow_requests_requester_id", table_name="borrow_requests")
    op.drop_table("borrow_requests")

    op.drop_index("ix_group_hierarchy_edges_child_group_id", table_name="group_hierarchy_edges")
    op.drop_index("ix_group_hierarchy_edges_parent_group_id", table_name="group_hierarchy_edges")
    op.drop_table("group_hierarchy_edges")

    op.drop_index("ix_hardware_change_logs_created_at", table_name="hardware_change_logs")
    op.drop_index("ix_hardware_change_logs_source_request_id", table_name="hardware_change_logs")
    op.drop_index("ix_hardware_change_logs_source", table_name="hardware_change_logs")
    op.drop_index("ix_hardware_change_logs_field_name", table_name="hardware_change_logs")
    op.drop_index("ix_hardware_change_logs_setup_id", table_name="hardware_change_logs")
    op.drop_table("hardware_change_logs")

    op.drop_index("ix_setup_hardware_baseline_setup_id", table_name="setup_hardware_baseline")
    op.drop_table("setup_hardware_baseline")
