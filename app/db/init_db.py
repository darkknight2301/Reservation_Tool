"""
Database seeding routine: creates all Roles and Permissions (and their
mapping) from the ``DEFAULT_ROLE_PERMISSIONS`` data in ``app.core.constants``
if they do not already exist. Idempotent -- safe to run on every startup or
deploy.
"""
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_ROLE_PERMISSIONS, PermissionCode
from app.core.logging_config import get_logger
from app.models.permission import Permission
from app.models.role import Role

logger = get_logger(__name__)

_PERMISSION_DESCRIPTIONS = {
    PermissionCode.USER_MANAGE: "Create, update, and deactivate user accounts.",
    PermissionCode.USER_APPROVE: "Approve or reject pending user registrations.",
    PermissionCode.USER_VIEW: "View user accounts.",
    PermissionCode.PRODUCT_MANAGE: "Create, update, and delete products and setups.",
    PermissionCode.PRODUCT_VIEW: "View products and setups.",
    PermissionCode.GROUP_MANAGE: "Create, update, and delete groups.",
    PermissionCode.GROUP_VIEW: "View groups.",
    PermissionCode.RESERVATION_CREATE: "Create reservations.",
    PermissionCode.RESERVATION_CANCEL_OWN: "Cancel one's own reservations.",
    PermissionCode.RESERVATION_CANCEL_ANY: "Cancel any user's reservation.",
    PermissionCode.RESERVATION_VIEW: "View reservations.",
    PermissionCode.SWAP_REQUEST: "Request a setup swap.",
    PermissionCode.SWAP_APPROVE: "Approve or reject swap requests.",
    PermissionCode.SWAP_VIEW: "View swap requests.",
    PermissionCode.ANNOUNCEMENT_MANAGE: "Create, update, and delete announcements.",
    PermissionCode.ANNOUNCEMENT_VIEW: "View announcements.",
    PermissionCode.AUDIT_VIEW: "View the audit log.",
    PermissionCode.LOGS_VIEW: "View and download the Developer Logs (rotating Excel transaction logs).",
    PermissionCode.LOGS_VIEW: "View and download Developer Logs (rotating Excel transaction logs).",
    PermissionCode.EXPORT_RUN: "Run Excel exports.",
    PermissionCode.IMPORT_RUN: "Run Excel imports.",
}


def seed_roles_and_permissions(db: Session) -> None:
    """Idempotently seed every Permission and Role, and the role-permission mapping."""
    permission_by_code = {}
    for code in PermissionCode.ALL:
        permission = db.query(Permission).filter(Permission.code == code).first()
        if permission is None:
            permission = Permission(code=code, description=_PERMISSION_DESCRIPTIONS.get(code, ""))
            db.add(permission)
            db.flush()
            logger.info("Seeded permission '{0}'.".format(code))
        permission_by_code[code] = permission

    for role_name, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            role = Role(name=role_name, description="{0} role".format(role_name.replace("_", " ").title()))
            db.add(role)
            db.flush()
            logger.info("Seeded role '{0}'.".format(role_name))

        existing_codes = {permission.code for permission in role.permissions}
        for code in permission_codes:
            if code not in existing_codes:
                role.permissions.append(permission_by_code[code])

    db.commit()
