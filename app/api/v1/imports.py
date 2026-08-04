"""Excel import endpoints for Setups."""
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import get_import_service, require_permission
from app.core.constants import PermissionCode
from app.models.user import User
from app.schemas.export_import import ImportResultResponse
from app.services.import_service import ImportService

router = APIRouter(prefix="/imports", tags=["Imports"])


@router.post("/setups", response_model=ImportResultResponse)
async def import_setups(
    file: UploadFile,
    current_user: User = Depends(require_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
) -> ImportResultResponse:
    """
    Bulk-import Setups from an uploaded Excel workbook. Requires
    ``import:run``. The import is all-or-nothing: if any row fails
    validation, no rows are committed and a full error report is returned.
    """
    temp_path = os.path.join(tempfile.gettempdir(), "setup_import_{0}.xlsx".format(uuid.uuid4().hex))
    contents = await file.read()
    with open(temp_path, "wb") as temp_file:
        temp_file.write(contents)

    try:
        return import_service.import_setups(temp_path, current_user)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
