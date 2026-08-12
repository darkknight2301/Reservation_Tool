"""Excel import endpoints for Setups."""
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, UploadFile

from app.api.deps import get_import_service, get_role_lookup_service, require_permission
from app.core.constants import PermissionCode
from app.core.exceptions import AuthorizationError
from app.models.user import User
from app.schemas.export_import import ImportResultResponse
from app.schemas.template import DetectedColumnsResponse
from app.services.import_service import ImportService
from app.services.role_lookup_service import RoleLookupService

router = APIRouter(prefix="/imports", tags=["Imports"])


async def _write_temp_upload(file: UploadFile) -> str:
    temp_path = os.path.join(tempfile.gettempdir(), "setup_import_{0}.xlsx".format(uuid.uuid4().hex))
    contents = await file.read()
    with open(temp_path, "wb") as temp_file:
        temp_file.write(contents)
    return temp_path


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


@router.post("/setups/product/{product_id}/detect-columns", response_model=DetectedColumnsResponse)
async def detect_setup_import_columns(
    product_id: int,
    file: UploadFile,
    current_user: User = Depends(require_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
) -> DetectedColumnsResponse:
    """
    Preview an uploaded workbook against a Product's current template: which
    headers are already known vs. brand new. Does not import anything.
    Requires ``import:run``.
    """
    temp_path = await _write_temp_upload(file)
    try:
        return import_service.detect_new_columns(temp_path, product_id)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/setups/product/{product_id}", response_model=ImportResultResponse)
async def import_setups_for_product(
    product_id: int,
    file: UploadFile,
    accept_new_columns: bool = False,
    current_user: User = Depends(require_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
    role_lookup_service: RoleLookupService = Depends(get_role_lookup_service),
) -> ImportResultResponse:
    """
    Bulk-import Setups for a single, pre-selected Product using that
    Product's current template. If the workbook contains columns not yet in
    the template, the import is rejected (``committed=false``,
    ``new_columns`` populated) unless ``accept_new_columns=true``, in which
    case the new columns are added to the template ("Add to Template &
    Import") before the rows are committed. Requires ``import:run``;
    accepting new columns additionally requires ``product:manage``.
    """
    if accept_new_columns and not role_lookup_service.role_has_permission(current_user.role, PermissionCode.PRODUCT_MANAGE):
        raise AuthorizationError("Adding new columns to a template requires product:manage.")

    temp_path = await _write_temp_upload(file)
    try:
        return import_service.import_setups_for_product(temp_path, product_id, current_user, accept_new_columns)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
