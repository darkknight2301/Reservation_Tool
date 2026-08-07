"""
Shared FastAPI dependencies: repository/service DI wiring, current-user
resolution, and permission-check dependency factories.
"""
from typing import Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.sqlalchemy.announcement_repository import AnnouncementRepository
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.export_repository import ExportRepository
from app.repositories.sqlalchemy.group_repository import GroupRepository
from app.repositories.sqlalchemy.product_repository import ProductRepository
from app.repositories.sqlalchemy.refresh_token_repository import RefreshTokenRepository
from app.repositories.sqlalchemy.reservation_repository import ReservationRepository
from app.repositories.sqlalchemy.role_repository import RoleRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.repositories.sqlalchemy.swap_repository import SwapRepository
from app.repositories.sqlalchemy.user_repository import UserRepository
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.developer_logs_service import DeveloperLogsService
from app.services.email_service import EmailService
from app.services.export_service import ExportService
from app.services.group_service import GroupService
from app.services.import_service import ImportService
from app.services.notification_service import NotificationService
from app.services.product_service import ProductService
from app.services.reservation_service import ReservationService
from app.services.role_lookup_service import RoleLookupService
from app.services.setup_service import SetupService
from app.services.swap_service import SwapService
from app.services.user_service import UserService


# --- Repository providers -------------------------------------------------

def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_role_repository(db: Session = Depends(get_db)) -> RoleRepository:
    return RoleRepository(db)


def get_refresh_token_repository(db: Session = Depends(get_db)) -> RefreshTokenRepository:
    return RefreshTokenRepository(db)


def get_product_repository(db: Session = Depends(get_db)) -> ProductRepository:
    return ProductRepository(db)


def get_group_repository(db: Session = Depends(get_db)) -> GroupRepository:
    return GroupRepository(db)


def get_setup_repository(db: Session = Depends(get_db)) -> SetupRepository:
    return SetupRepository(db)


def get_reservation_repository(db: Session = Depends(get_db)) -> ReservationRepository:
    return ReservationRepository(db)


def get_swap_repository(db: Session = Depends(get_db)) -> SwapRepository:
    return SwapRepository(db)


def get_announcement_repository(db: Session = Depends(get_db)) -> AnnouncementRepository:
    return AnnouncementRepository(db)


def get_audit_repository(db: Session = Depends(get_db)) -> AuditLogRepository:
    return AuditLogRepository(db)


def get_export_repository(db: Session = Depends(get_db)) -> ExportRepository:
    return ExportRepository(db)


# --- Service providers -----------------------------------------------------

def get_audit_service(audit_repository: AuditLogRepository = Depends(get_audit_repository)) -> AuditService:
    return AuditService(audit_repository)


def get_role_lookup_service(role_repository: RoleRepository = Depends(get_role_repository)) -> RoleLookupService:
    return RoleLookupService(role_repository)


def get_email_service() -> EmailService:
    return EmailService()


def get_notification_service(
    announcement_repository: AnnouncementRepository = Depends(get_announcement_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    audit_service: AuditService = Depends(get_audit_service),
    email_service: EmailService = Depends(get_email_service),
) -> NotificationService:
    announcement_service = AnnouncementService(announcement_repository, audit_service)
    return NotificationService(announcement_service, email_service, user_repository)


def get_developer_logs_service() -> DeveloperLogsService:
    return DeveloperLogsService()


def get_auth_service(
    user_repository: UserRepository = Depends(get_user_repository),
    refresh_token_repository: RefreshTokenRepository = Depends(get_refresh_token_repository),
    role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuthService:
    return AuthService(user_repository, refresh_token_repository, role_lookup_service, audit_service)


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UserService:
    return UserService(user_repository, role_lookup_service, audit_service)


def get_product_service(
    product_repository: ProductRepository = Depends(get_product_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> ProductService:
    return ProductService(product_repository, audit_service)


def get_group_service(
    group_repository: GroupRepository = Depends(get_group_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> GroupService:
    return GroupService(group_repository, audit_service)


def get_setup_service(
    setup_repository: SetupRepository = Depends(get_setup_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> SetupService:
    return SetupService(setup_repository, audit_service)


def get_reservation_service(
    reservation_repository: ReservationRepository = Depends(get_reservation_repository),
    setup_repository: SetupRepository = Depends(get_setup_repository),
    role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
    audit_service: AuditService = Depends(get_audit_service),
    swap_repository: SwapRepository = Depends(get_swap_repository),
    notification_service: NotificationService = Depends(get_notification_service),
) -> ReservationService:
    return ReservationService(reservation_repository, setup_repository, role_lookup_service, audit_service, swap_repository, notification_service)


def get_swap_service(
    swap_repository: SwapRepository = Depends(get_swap_repository),
    reservation_repository: ReservationRepository = Depends(get_reservation_repository),
    setup_repository: SetupRepository = Depends(get_setup_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> SwapService:
    return SwapService(swap_repository, reservation_repository, setup_repository, audit_service)


def get_announcement_service(
    announcement_repository: AnnouncementRepository = Depends(get_announcement_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> AnnouncementService:
    return AnnouncementService(announcement_repository, audit_service)


def get_export_service(
    export_repository: ExportRepository = Depends(get_export_repository),
    setup_repository: SetupRepository = Depends(get_setup_repository),
    reservation_repository: ReservationRepository = Depends(get_reservation_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> ExportService:
    return ExportService(export_repository, setup_repository, reservation_repository, audit_service)


def get_import_service(
    setup_repository: SetupRepository = Depends(get_setup_repository),
    product_repository: ProductRepository = Depends(get_product_repository),
    group_repository: GroupRepository = Depends(get_group_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    export_repository: ExportRepository = Depends(get_export_repository),
    audit_service: AuditService = Depends(get_audit_service),
) -> ImportService:
    return ImportService(
        setup_repository, product_repository, group_repository, user_repository, export_repository, audit_service
    )


# --- Authentication / RBAC dependencies -----------------------------------

def get_current_user(
    authorization: str = Header(default=None),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """
    Resolve the current authenticated user from the ``Authorization: Bearer``
    header, re-fetching the user from the database on every request so
    deactivation/role changes take effect immediately (see architecture
    document, section 6).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise AuthenticationError("Token is missing a subject claim.")

    user = user_repository.get_by_id(int(user_id_raw))
    if user is None or not user.is_active:
        raise AuthenticationError("Account is no longer active.")

    return user


def require_permission(permission_code: str) -> Callable[..., User]:
    """
    Dependency factory: returns a dependency that ensures the current user's
    role carries the given permission code, raising AuthorizationError
    otherwise.
    """

    def _check(
        current_user: User = Depends(get_current_user),
        role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
    ) -> User:
        if not role_lookup_service.role_has_permission(current_user.role, permission_code):
            raise AuthorizationError("You do not have permission to perform this action.")
        return current_user

    return _check
