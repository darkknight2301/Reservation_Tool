"""
Model registry.

Importing every model module here ensures all classes are registered on
``Base.metadata`` before Alembic autogenerate or ``Base.metadata.create_all``
runs, and before SQLAlchemy resolves string-based ``relationship()``
references between models.
"""
from app.models.announcement import Announcement  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.excel_transaction_log import ExcelTransactionLog  # noqa: F401
from app.models.export_log import ExportLog  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.permission import Permission, role_permissions  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.product_template_column import ProductTemplateColumn  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.reservation import Reservation  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.setup import Setup  # noqa: F401
from app.models.setup_custom_field_value import SetupCustomFieldValue  # noqa: F401
from app.models.swap_request import SwapRequest  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_group import user_groups  # noqa: F401

__all__ = [
    "Announcement",
    "AuditLog",
    "ExcelTransactionLog",
    "ExportLog",
    "Group",
    "Permission",
    "role_permissions",
    "Product",
    "ProductTemplateColumn",
    "RefreshToken",
    "Reservation",
    "Role",
    "Setup",
    "SetupCustomFieldValue",
    "SwapRequest",
    "User",
    "user_groups",
]
