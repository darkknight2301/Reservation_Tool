"""
Central definition of enumerations and constant values used throughout the
application. Keeping these in one module avoids "magic string" duplication
across services, repositories, and schemas, and gives a single place to
extend the permission matrix or add a new status value.
"""
from typing import Dict, List


class RoleName:
    """
    Canonical role names, stored in the ``roles.name`` column.

    Renamed (this revision): the tier historically called "User" is now
    "Bot", "Developer" is now "User", and "Developer Lead" is now
    "Manager" (Lead and Owner are unchanged). The attribute names below
    are kept stable for backward compatibility -- each still identifies
    the exact same permission tier as before; only the stored/displayed
    string value changed.
    """

    USER = "BOT"                # formerly the "USER" role; view-only tier
    DEVELOPER = "USER"           # formerly the "DEVELOPER" role; can reserve/swap-request/export
    LEAD = "LEAD"                 # unchanged
    DEVELOPER_LEAD = "MANAGER"     # formerly the "DEVELOPER_LEAD" role; full admin short of Owner
    OWNER = "OWNER"                # unchanged

    # Preferred names going forward -- identical values to their legacy
    # counterparts above, kept in sync automatically.
    BOT = USER
    MANAGER = DEVELOPER_LEAD

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
    RoleName.USER: [  # "Bot": view-only
        PermissionCode.PRODUCT_VIEW,
        PermissionCode.GROUP_VIEW,
        PermissionCode.RESERVATION_VIEW,
        PermissionCode.SWAP_VIEW,
        PermissionCode.ANNOUNCEMENT_VIEW,
    ],
    RoleName.DEVELOPER: [  # "User": can reserve/swap-request/export
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
        PermissionCode.EXPORT_RUN,
        PermissionCode.IMPORT_RUN,
        # LOGS_VIEW intentionally NOT granted -- Lead no longer sees Developer Logs.
    ],
    RoleName.DEVELOPER_LEAD: [  # "Manager": full admin short of Owner
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


class ColumnDataType:
    """Supported data types for a product's custom template columns."""

    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    DROPDOWN = "DROPDOWN"

    ALL = (STRING, INTEGER, FLOAT, BOOLEAN, DATE, DATETIME, DROPDOWN)


# The columns every Product's table/template always has, in canonical
# display order. These map onto existing, already-persisted fields (Setup
# columns or the Setup's active Reservation) rather than anything stored in
# ``product_template_columns`` -- they can never be renamed, deleted, or
# reordered, and a product's custom columns are always appended after them.
MANDATORY_TEMPLATE_COLUMNS: List[Dict[str, str]] = [
    {"name": "ip", "label": "IP"},
    {"name": "user", "label": "User"},
    {"name": "owner", "label": "Owner"},
    {"name": "reservation", "label": "Reservation"},
    {"name": "remark", "label": "Remark"},
    {"name": "location", "label": "Location"},
    {"name": "group", "label": "Group"},
    {"name": "product", "label": "Product"},
]
MANDATORY_TEMPLATE_COLUMN_NAMES = tuple(col["name"] for col in MANDATORY_TEMPLATE_COLUMNS)


class ExportType:
    """Kinds of Excel exports supported by the export service."""

    SETUPS = "SETUPS"
    RESERVATIONS = "RESERVATIONS"
    AUDIT_LOGS = "AUDIT_LOGS"

    ALL = (SETUPS, RESERVATIONS, AUDIT_LOGS)
