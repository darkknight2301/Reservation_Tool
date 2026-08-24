"""Role rename: User->Bot, Developer->User, Developer Lead->Manager; Lead loses logs:view.

Renames existing ``roles`` rows in place (same row id, so every
``users.role_id`` FK keeps pointing at the correct, now-relabeled role --
no user data is lost or reassigned). Also removes the ``logs:view`` grant
from the LEAD role, since the idempotent seeder only ever adds permissions,
never removes them.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-24 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
permissions = sa.table("permissions", sa.column("id", sa.Integer), sa.column("code", sa.String))
role_permissions = sa.table(
    "role_permissions", sa.column("role_id", sa.Integer), sa.column("permission_id", sa.Integer)
)


def upgrade() -> None:
    # Order matters: vacate "USER" (-> "BOT") before "DEVELOPER" claims it (-> "USER").
    op.execute(roles.update().where(roles.c.name == "USER").values(name="BOT"))
    op.execute(roles.update().where(roles.c.name == "DEVELOPER").values(name="USER"))
    op.execute(roles.update().where(roles.c.name == "DEVELOPER_LEAD").values(name="MANAGER"))

    connection = op.get_bind()
    lead_role_id = connection.execute(sa.select(roles.c.id).where(roles.c.name == "LEAD")).scalar()
    logs_view_permission_id = connection.execute(
        sa.select(permissions.c.id).where(permissions.c.code == "logs:view")
    ).scalar()
    if lead_role_id is not None and logs_view_permission_id is not None:
        op.execute(
            role_permissions.delete().where(
                sa.and_(
                    role_permissions.c.role_id == lead_role_id,
                    role_permissions.c.permission_id == logs_view_permission_id,
                )
            )
        )


def downgrade() -> None:
    op.execute(roles.update().where(roles.c.name == "MANAGER").values(name="DEVELOPER_LEAD"))
    op.execute(roles.update().where(roles.c.name == "USER").values(name="DEVELOPER"))
    op.execute(roles.update().where(roles.c.name == "BOT").values(name="USER"))

    connection = op.get_bind()
    lead_role_id = connection.execute(sa.select(roles.c.id).where(roles.c.name == "LEAD")).scalar()
    logs_view_permission_id = connection.execute(
        sa.select(permissions.c.id).where(permissions.c.code == "logs:view")
    ).scalar()
    if lead_role_id is not None and logs_view_permission_id is not None:
        op.execute(
            role_permissions.insert().values(role_id=lead_role_id, permission_id=logs_view_permission_id)
        )
