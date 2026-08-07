"""Excel export endpoints for Setups and Reservations."""
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_export_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.reservation import ReservationFilter
from app.schemas.setup import SetupFilter
from app.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.post("/setups")
def export_setups(
    product_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    current_user: User = Depends(require_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
) -> FileResponse:
    """Export Setups matching the given filters to an Excel workbook. Requires ``export:run``."""
    filters = SetupFilter(product_id=product_id, group_id=group_id, status=status, location=location)
    export_log = export_service.export_setups(filters, current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/setups/template")
def export_setups_template(
    current_user: User = Depends(require_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
) -> FileResponse:
    """Generate and download an empty, import-ready Setup template. Requires ``export:run``."""
    export_log = export_service.generate_setup_template(current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/reservations")
def export_reservations(
    user_id: Optional[int] = None,
    setup_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
) -> FileResponse:
    """Export Reservations matching the given filters to an Excel workbook. Requires ``export:run``."""
    filters = ReservationFilter(user_id=user_id, setup_id=setup_id, status=status)
    export_log = export_service.export_reservations(filters, current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
