"""Dashboard screen: summary cards and active announcements."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    get_announcement_service,
    get_reservation_service,
    get_role_lookup_service,
    get_setup_service,
    get_user_service,
)
from app.core.constants import PermissionCode, ReservationStatus, SetupStatus, UserStatus
from app.models.user import User
from app.schemas.announcement import AnnouncementFilter
from app.schemas.reservation import ReservationFilter
from app.schemas.setup import SetupFilter
from app.schemas.user import UserFilter
from app.services.announcement_service import AnnouncementService
from app.services.reservation_service import ReservationService
from app.services.role_lookup_service import RoleLookupService
from app.services.setup_service import SetupService
from app.services.user_service import UserService
from app.web.deps import base_context, get_current_web_user, templates

router = APIRouter(tags=["Web - Dashboard"])


@router.get("/")
@router.get("/dashboard")
def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_web_user),
    setup_service: SetupService = Depends(get_setup_service),
    reservation_service: ReservationService = Depends(get_reservation_service),
    announcement_service: AnnouncementService = Depends(get_announcement_service),
    user_service: UserService = Depends(get_user_service),
    role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
):
    """Render the dashboard: setup availability, my reservations, pending approvals, announcements."""
    _, total_setups = setup_service.list(SetupFilter(), page=1, page_size=1)
    _, available_setups = setup_service.list(SetupFilter(status=SetupStatus.AVAILABLE), page=1, page_size=1)
    _, my_reservations = reservation_service.list(
        ReservationFilter(user_id=current_user.id, status=ReservationStatus.ACTIVE), page=1, page_size=1
    )

    pending_approvals = 0
    if role_lookup_service.role_has_permission(current_user.role, PermissionCode.USER_APPROVE):
        _, pending_approvals = user_service.list(UserFilter(status=UserStatus.PENDING), page=1, page_size=1)

    announcements, _ = announcement_service.list(AnnouncementFilter(active_only=True), page=1, page_size=10)

    context = base_context(request, current_user)
    context.update(
        {
            "total_setups": total_setups,
            "available_setups": available_setups,
            "my_reservations": my_reservations,
            "pending_approvals": pending_approvals,
            "announcements": announcements,
        }
    )
    return templates.TemplateResponse("dashboard/index.html", context)
