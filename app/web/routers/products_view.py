"""Product selection screen (card grid) and the Product Management admin screen."""
import json
import os
import tempfile
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_export_service, get_import_service, get_product_service, get_setup_service
from app.core.constants import PermissionCode, SetupStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.schemas.setup import SetupFilter
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.product_service import ProductService
from app.services.setup_service import SetupService
from app.web.deps import base_context, get_current_web_user, require_web_permission, templates

router = APIRouter(tags=["Web - Products"])


@router.get("/products")
def product_selection_page(
    request: Request,
    current_user: User = Depends(get_current_web_user),
    product_service: ProductService = Depends(get_product_service),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Render a card grid of Products, each showing its setup counts."""
    products, _ = product_service.list(page=1, page_size=100)

    product_cards = []
    for product in products:
        _, total = setup_service.list(SetupFilter(product_id=product.id), page=1, page_size=1)
        _, available = setup_service.list(SetupFilter(product_id=product.id, status=SetupStatus.AVAILABLE), page=1, page_size=1)
        product_cards.append({"product": product, "total": total, "available": available})

    context = base_context(request, current_user)
    context.update({"product_cards": product_cards})
    return templates.TemplateResponse("products/select.html", context)


@router.get("/admin/products")
def product_management_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Render the Product Management admin screen."""
    products, _ = product_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"products": products})
    return templates.TemplateResponse("admin/products.html", context)


@router.get("/admin/products/list")
def product_list_partial(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """HTMX partial: re-render the Product list table."""
    products, _ = product_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"products": products})
    return templates.TemplateResponse("admin/_products_list.html", context)


@router.get("/admin/products/form")
def product_form_dialog(
    request: Request,
    product_id: Optional[int] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Render the create/edit Product modal."""
    product = product_service.get_by_id(product_id) if product_id else None
    context = base_context(request, current_user)
    context.update({"product": product})
    return templates.TemplateResponse("admin/_product_form_modal.html", context)


@router.post("/admin/products/save")
def product_save(
    request: Request,
    product_id: str = Form(default=""),
    name: str = Form(...),
    description: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Create or update a Product, then re-render the list."""
    message = "Product saved successfully."
    try:
        if product_id:
            product_service.update(int(product_id), ProductUpdateRequest(name=name, description=description or None), current_user)
        else:
            product_service.create(ProductCreateRequest(name=name, description=description or None), current_user)
    except AppError as exc:
        message = exc.message

    products, _ = product_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"products": products})
    response = templates.TemplateResponse("admin/_products_list.html", context)
    response.headers["HX-Trigger"] = _toast_and_close(message)
    return response


@router.delete("/admin/products/{product_id}")
def product_delete(
    request: Request,
    product_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
):
    """Delete a Product, then re-render the list."""
    message, message_type = "Product deleted successfully.", "success"
    try:
        product_service.delete(product_id, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    products, _ = product_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"products": products})
    response = templates.TemplateResponse("admin/_products_list.html", context)
    response.headers["HX-Trigger"] = _toast(message, message_type)
    return response


@router.get("/admin/products/{product_id}/export")
def export_product_setups(
    product_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
):
    """Export every Setup for a given Product (auto-generates a template if it has none). Requires ``export:run``."""
    export_log = export_service.export_setups(SetupFilter(product_id=product_id), current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _toast(message: str, message_type: str) -> str:
    return json.dumps({"showToast": {"message": message, "type": message_type}})


def _toast_and_close(message: str) -> str:
    return json.dumps({"showToast": {"message": message, "type": "success"}, "closeDialog": {}})


@router.get("/admin/setups/template")
def download_setup_template(
    current_user: User = Depends(require_web_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
):
    """Download a blank, import-ready Setup template."""
    export_log = export_service.generate_setup_template(current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/admin/setups/import-dialog")
def setup_import_dialog(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.IMPORT_RUN)),
):
    """Render the Setup Excel import upload modal."""
    context = base_context(request, current_user)
    return templates.TemplateResponse("admin/_setup_import_modal.html", context)


@router.post("/admin/setups/import")
async def setup_import_submit(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(require_web_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
    product_service: ProductService = Depends(get_product_service),
):
    """Process an uploaded Setup Excel workbook (all-or-nothing) and report the result."""
    temp_path = os.path.join(tempfile.gettempdir(), "setup_import_{0}.xlsx".format(uuid.uuid4().hex))
    contents = await file.read()
    with open(temp_path, "wb") as temp_file:
        temp_file.write(contents)

    try:
        result = import_service.import_setups(temp_path, current_user)
    except AppError as exc:
        context = base_context(request, current_user)
        context.update({"import_error": exc.message})
        response = templates.TemplateResponse("admin/_setup_import_result.html", context)
        response.headers["HX-Trigger"] = _toast(exc.message, "error")
        return response
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    context = base_context(request, current_user)
    context.update({"result": result})
    response = templates.TemplateResponse("admin/_setup_import_result.html", context)
    if result.committed:
        message = "Import complete: {0} created, {1} updated.".format(result.created_count, result.updated_count)
        response.headers["HX-Trigger"] = _toast(message, "success")
    else:
        response.headers["HX-Trigger"] = _toast(
            "Import rejected: {0} row error(s) found. No rows were committed.".format(result.error_count), "warning"
        )
    return response
