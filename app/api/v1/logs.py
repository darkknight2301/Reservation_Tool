"""Developer Logs endpoints: directory tree of rotating Excel transaction logs, and file download."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_developer_logs_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.services.developer_logs_service import DeveloperLogsService

router = APIRouter(prefix="/dev-logs", tags=["Developer Logs"])


@router.get("/tree")
def get_logs_tree(
    _current_user: User = Depends(require_permission(PermissionCode.LOGS_VIEW)),
    developer_logs_service: DeveloperLogsService = Depends(get_developer_logs_service),
) -> dict:
    """Return the Logs/ directory tree (Month_Year folders and their rotated Excel log files)."""
    return developer_logs_service.build_tree()


@router.get("/download")
def download_log_file(
    path: str,
    _current_user: User = Depends(require_permission(PermissionCode.LOGS_VIEW)),
    developer_logs_service: DeveloperLogsService = Depends(get_developer_logs_service),
) -> FileResponse:
    """Download a specific rotated Excel log file by its relative path."""
    absolute_path = developer_logs_service.resolve_download_path(path)
    return FileResponse(
        path=absolute_path,
        filename=absolute_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
