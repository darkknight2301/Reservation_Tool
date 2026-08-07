"""Developer Logs screen: tree view of rotating Excel transaction logs, with download links."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.core.constants import PermissionCode
from app.models.user import User
from app.services.developer_logs_service import DeveloperLogsService
from app.web.deps import base_context, require_web_permission, templates

router = APIRouter(tags=["Web - Developer Logs"])


def get_developer_logs_service() -> DeveloperLogsService:
    return DeveloperLogsService()


@router.get("/admin/developer-logs")
def developer_logs_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.LOGS_VIEW)),
    developer_logs_service: DeveloperLogsService = Depends(get_developer_logs_service),
):
    """Render the Developer Logs tree view."""
    tree = developer_logs_service.build_tree()
    context = base_context(request, current_user)
    context.update({"tree": tree})
    return templates.TemplateResponse("admin/developer_logs.html", context)


@router.get("/admin/developer-logs/download")
def developer_logs_download(
    path: str,
    current_user: User = Depends(require_web_permission(PermissionCode.LOGS_VIEW)),
    developer_logs_service: DeveloperLogsService = Depends(get_developer_logs_service),
):
    """Download a specific rotated Excel log file by its relative path."""
    absolute_path = developer_logs_service.resolve_download_path(path)
    return FileResponse(
        path=absolute_path,
        filename=absolute_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
