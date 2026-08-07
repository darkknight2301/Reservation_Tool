"""
Central definition of enumerations and constant values used throughout the
application. Keeping these in one module avoids "magic string" duplication
across services, repositories, and schemas, and gives a single place to
extend the permission matrix or add a new status value.
"""
from typing import Dict, List


class RoleName:
    """Canonical role names. Stored in the ``roles.name`` column."""

    USER = "USER"
    DEVELOPER = "DEVELOPER"
    LEAD = "LEAD"
    DEVELOPER_LEAD = "DEVELOPER_LEAD"
    OWNER = "OWNER"

    ALL = (USER, DEVELOPER, LEAD, DEVELOPER_LEAD, OWNER)


class PermissionCode:
    """Canonical permission codes. Stored in the ``permissions.code`` column."""

    USER_MANAGE = "user:manage"
    USER_APPROVE = "user:approve"
    USER_VIEW = "user:view"

    PRODUCT_MANAGE = "product:manage"
    PRODUCT_VIEW = "product:view"

    GROUP_MANAGE = "group:manage"
    GROUP_VIEW = "group:view"

    RESERVATION_CREATE = "reservation:create"
    RESERVATION_CANCEL_OWN = "reservation:cancel_own"
    RESERVATION_CANCEL_ANY = "reservation:cancel_any"
    RESERVATION_VIEW = "reservation:view"

    SWAP_REQUEST = "swap:request"
    SWAP_APPROVE = "swap:approve"
    SWAP_VIEW = "swap:view"

    ANNOUNCEMENT_MANAGE = "announcement:manage"
    ANNOUNCEMENT_VIEW = "announcement:view"

    AUDIT_VIEW = "audit:view"

    LOGS_VIEW = "logs:view"

    EXPORT_RUN = "export:run"
    IMPORT_RUN = "import:run"

    ALL = (
        USER_MANAGE,
        USER_APPROVE,
        USER_VIEW,
        PRODUCT_MANAGE,
        PRODUCT_VIEW,
        GROUP_MANAGE,
        GROUP_VIEW,
        RESERVATION_CREATE,
        RESERVATION_CANCEL_OWN,
        RESERVATION_CANCEL_ANY,
        RESERVATION_VIEW,
        SWAP_REQUEST,
        SWAP_APPROVE,
        SWAP_VIEW,
        ANNOUNCEMENT_MANAGE,
        ANNOUNCEMENT_VIEW,
        AUDIT_VIEW,
        LOGS_VIEW,
        EXPORT_RUN,
        IMPORT_RUN,
    )


class AnnouncementChannel:
    """Broadcast channels selectable when creating a reservation (or an announcement directly)."""

    WALL = "WALL"
    MAIL_LEADS = "MAIL_LEADS"
    MAIL_GROUP = "MAIL_GROUP"
    MAIL_ALL = "MAIL_ALL"

    ALL = (WALL, MAIL_LEADS, MAIL_GROUP, MAIL_ALL)


# Default role -> permission matrix used by the database seeding routine.
# Expressed as data (not code branches) so that changing a role's
# capabilities is a seed-data change, not a code change.
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    RoleName.USER: [
        PermissionCode.PRODUCT_VIEW,
        PermissionCode.GROUP_VIEW,
        PermissionCode.RESERVATION_VIEW,
        PermissionCode.SWAP_VIEW,
        PermissionCode.ANNOUNCEMENT_VIEW,
    ],
    RoleName.DEVELOPER: [
        PermissionCode.PRODUCT_VIEW,
        PermissionCode.GROUP_VIEW,
        PermissionCode.RESERVATION_CREATE,
        PermissionCode.RESERVATION_CANCEL_OWN,
        PermissionCode.RESERVATION_VIEW,
        PermissionCode.SWAP_REQUEST,
        PermissionCode.SWAP_VIEW,
        PermissionCode.ANNOUNCEMENT_VIEW,
        PermissionCode.EXPORT_RUN,
    ],
    RoleName.LEAD: [
        PermissionCode.USER_APPROVE,
        PermissionCode.PRODUCT_VIEW,
        PermissionCode.GROUP_MANAGE,
        PermissionCode.GROUP_VIEW,
        PermissionCode.RESERVATION_CREATE,
        PermissionCode.RESERVATION_CANCEL_OWN,
        PermissionCode.RESERVATION_CANCEL_ANY,
        PermissionCode.RESERVATION_VIEW,
        PermissionCode.SWAP_REQUEST,
        PermissionCode.SWAP_APPROVE,
        PermissionCode.SWAP_VIEW,
        PermissionCode.ANNOUNCEMENT_VIEW,
        PermissionCode.LOGS_VIEW,
        PermissionCode.EXPORT_RUN,
        PermissionCode.IMPORT_RUN,
    ],
    RoleName.DEVELOPER_LEAD: [
        PermissionCode.USER_MANAGE,
        PermissionCode.USER_APPROVE,
        PermissionCode.USER_VIEW,
        PermissionCode.PRODUCT_MANAGE,
        PermissionCode.PRODUCT_VIEW,
        PermissionCode.GROUP_MANAGE,
        PermissionCode.GROUP_VIEW,
        PermissionCode.RESERVATION_CREATE,
        PermissionCode.RESERVATION_CANCEL_OWN,
        PermissionCode.RESERVATION_CANCEL_ANY,
        PermissionCode.RESERVATION_VIEW,
        PermissionCode.SWAP_REQUEST,
        PermissionCode.SWAP_APPROVE,
        PermissionCode.SWAP_VIEW,
        PermissionCode.ANNOUNCEMENT_MANAGE,
        PermissionCode.ANNOUNCEMENT_VIEW,
        PermissionCode.AUDIT_VIEW,
        PermissionCode.LOGS_VIEW,
        PermissionCode.EXPORT_RUN,
        PermissionCode.IMPORT_RUN,
    ],
    RoleName.OWNER: list(PermissionCode.ALL),
}


class UserStatus:
    """Lifecycle status of a user account (registration/approval workflow)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"

    ALL = (PENDING, APPROVED, REJECTED, DISABLED)


class SetupStatus:
    """Lifecycle status of a reservable setup."""

    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"
    RETIRED = "RETIRED"

    ALL = (AVAILABLE, RESERVED, MAINTENANCE, RETIRED)


class ReservationStatus:
    """Lifecycle status of a reservation."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SWAPPED = "SWAPPED"

    ALL = (ACTIVE, COMPLETED, CANCELLED, SWAPPED)


class SwapStatus:
    """Lifecycle status of a swap request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    ALL = (PENDING, APPROVED, REJECTED, CANCELLED)


class AnnouncementPriority:
    """Priority levels for announcements."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    ALL = (LOW, NORMAL, HIGH, CRITICAL)


class AuditAction:
    """Canonical action verbs recorded in the audit log."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    CANCEL = "CANCEL"
    SWAP = "SWAP"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class ExportType:
    """Kinds of Excel exports supported by the export service."""

    SETUPS = "SETUPS"
    RESERVATIONS = "RESERVATIONS"
    AUDIT_LOGS = "AUDIT_LOGS"

    ALL = (SETUPS, RESERVATIONS, AUDIT_LOGS)
