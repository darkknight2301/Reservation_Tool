"""Product selection screen (card grid) and the Product Management admin screen."""
import os
import tempfile
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import (
    get_export_service,
    get_import_service,
    get_product_service,
    get_setup_service,
    get_template_service,
)
from app.core.constants import ColumnDataType, PermissionCode, SetupStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.product import ProductCreateRequest, ProductUpdateRequest
from app.schemas.setup import SetupFilter
from app.schemas.template import TemplateColumnCreateRequest, TemplateColumnUpdateRequest
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.product_service import ProductService
from app.services.setup_service import SetupService
from app.services.template_service import TemplateService
from app.web.deps import base_context, get_current_web_user, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(tags=["Web - Products"])

# In-process handoff for the "New columns detected" Excel import confirmation
# step: a token maps to the temp file path so the confirm/reject step doesn't
# require re-uploading the workbook. Lightweight by design -- matches the
# rest of this admin UI's single-process HTMX flow.
_PENDING_PRODUCT_IMPORTS = {}


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
    message, message_type = "Product saved successfully.", "success"
    try:
        if product_id:
            product_service.update(int(product_id), ProductUpdateRequest(name=name, description=description or None), current_user)
        else:
            product_service.create(ProductCreateRequest(name=name, description=description or None), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    products, _ = product_service.list(page=1, page_size=200)
    context = base_context(request, current_user)
    context.update({"products": products})
    response = templates.TemplateResponse("admin/_products_list.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=(message_type == "success"))
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
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
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


@router.get("/admin/products/{product_id}/template")
def product_template_page(
    request: Request,
    product_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    product_service: ProductService = Depends(get_product_service),
    template_service: TemplateService = Depends(get_template_service),
):
    """Render the 'Design Template' screen for a Product. Requires ``product:manage``."""
    product = product_service.get_by_id(product_id)
    template = template_service.get_template(product_id)
    context = base_context(request, current_user)
    context.update({"product": product, "template": template, "column_types": ColumnDataType.ALL})
    return templates.TemplateResponse("admin/product_template.html", context)


@router.get("/admin/products/{product_id}/template/list")
def product_template_columns_partial(
    request: Request,
    product_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
):
    """HTMX partial: re-render the custom columns table."""
    template = template_service.get_template(product_id)
    context = base_context(request, current_user)
    context.update({"product_id": product_id, "template": template})
    return templates.TemplateResponse("admin/_product_template_columns.html", context)


@router.get("/admin/products/{product_id}/template/column-form")
def template_column_form_dialog(
    request: Request,
    product_id: int,
    column_id: Optional[int] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
):
    """Render the add/edit custom column modal."""
    column = None
    if column_id:
        template = template_service.get_template(product_id)
        column = next((c for c in template.custom_columns if c.id == column_id), None)
    context = base_context(request, current_user)
    context.update({"product_id": product_id, "column": column, "column_types": ColumnDataType.ALL})
    return templates.TemplateResponse("admin/_template_column_form_modal.html", context)


@router.post("/admin/products/{product_id}/template/save")
def template_column_save(
    request: Request,
    product_id: int,
    column_id: str = Form(default=""),
    name: str = Form(default=""),
    label: str = Form(default=""),
    data_type: str = Form(default=ColumnDataType.STRING),
    required: bool = Form(default=False),
    default_value: str = Form(default=""),
    allowed_values: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
):
    """Create or update a custom template column, then re-render the columns table."""
    message, message_type = "Column saved successfully.", "success"
    parsed_allowed = [v.strip() for v in allowed_values.split(",") if v.strip()] or None
    try:
        if column_id:
            template_service.update_column(
                product_id, int(column_id),
                TemplateColumnUpdateRequest(
                    label=label or None, required=required, default_value=default_value or None,
                    allowed_values=parsed_allowed,
                ),
                current_user,
            )
        else:
            template_service.add_column(
                product_id,
                TemplateColumnCreateRequest(
                    name=name, label=label or name, data_type=data_type, required=required,
                    default_value=default_value or None, allowed_values=parsed_allowed,
                ),
                current_user,
            )
    except AppError as exc:
        message, message_type = exc.message, "error"

    template = template_service.get_template(product_id)
    context = base_context(request, current_user)
    context.update({"product_id": product_id, "template": template})
    response = templates.TemplateResponse("admin/_product_template_columns.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=(message_type == "success"))
    return response


@router.delete("/admin/products/{product_id}/template/columns/{column_id}")
def template_column_delete(
    request: Request,
    product_id: int,
    column_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
):
    """Delete a custom template column, then re-render the columns table."""
    message, message_type = "Column deleted successfully.", "success"
    try:
        template_service.delete_column(product_id, column_id, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    template = template_service.get_template(product_id)
    context = base_context(request, current_user)
    context.update({"product_id": product_id, "template": template})
    response = templates.TemplateResponse("admin/_product_template_columns.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/admin/products/{product_id}/template/columns/{column_id}/move")
def template_column_move(
    request: Request,
    product_id: int,
    column_id: int,
    direction: str = Form(...),
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    template_service: TemplateService = Depends(get_template_service),
):
    """Move a custom column one position up/down, then re-render the columns table."""
    template = template_service.get_template(product_id)
    ordered_ids = [c.id for c in template.custom_columns]
    if column_id in ordered_ids:
        index = ordered_ids.index(column_id)
        target = index - 1 if direction == "up" else index + 1
        if 0 <= target < len(ordered_ids):
            ordered_ids[index], ordered_ids[target] = ordered_ids[target], ordered_ids[index]
            try:
                template_service.reorder_columns(product_id, ordered_ids, current_user)
            except AppError:
                pass

    template = template_service.get_template(product_id)
    context = base_context(request, current_user)
    context.update({"product_id": product_id, "template": template})
    return templates.TemplateResponse("admin/_product_template_columns.html", context)


@router.get("/admin/products/{product_id}/template/import-dialog")
def product_import_dialog(
    request: Request,
    product_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.IMPORT_RUN)),
    product_service: ProductService = Depends(get_product_service),
):
    """Render the product-scoped Setup Excel import upload modal."""
    product = product_service.get_by_id(product_id)
    context = base_context(request, current_user)
    context.update({"product": product})
    return templates.TemplateResponse("admin/_product_import_modal.html", context)


@router.post("/admin/products/{product_id}/template/import")
async def product_import_submit(
    request: Request,
    product_id: int,
    file: UploadFile,
    current_user: User = Depends(require_web_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
):
    """
    Process an uploaded, product-scoped Setup Excel workbook. If the
    workbook contains columns not yet in the product's template, the import
    is held (not committed) and a confirmation view is shown instead ("New
    columns detected") rather than silently ignoring them.
    """
    temp_path = os.path.join(tempfile.gettempdir(), "product_import_{0}.xlsx".format(uuid.uuid4().hex))
    contents = await file.read()
    with open(temp_path, "wb") as temp_file:
        temp_file.write(contents)

    try:
        result = import_service.import_setups_for_product(temp_path, product_id, current_user, accept_new_columns=False)
    except AppError as exc:
        os.remove(temp_path)
        context = base_context(request, current_user)
        context.update({"product_id": product_id, "import_error": exc.message})
        response = templates.TemplateResponse("admin/_product_import_result.html", context)
        response.headers["HX-Trigger"] = hx_trigger(exc.message, "error")
        return response

    context = base_context(request, current_user)
    if result.new_columns:
        token = uuid.uuid4().hex
        _PENDING_PRODUCT_IMPORTS[token] = temp_path
        context.update({"product_id": product_id, "result": result, "token": token})
    else:
        os.remove(temp_path)
        context.update({"product_id": product_id, "result": result})

    response = templates.TemplateResponse("admin/_product_import_result.html", context)
    if result.committed:
        message = "Import complete: {0} created, {1} updated.".format(result.created_count, result.updated_count)
        response.headers["HX-Trigger"] = hx_trigger(message, "success")
    elif not result.new_columns:
        response.headers["HX-Trigger"] = hx_trigger(
            "Import rejected: {0} row error(s) found. No rows were committed.".format(result.error_count), "warning"
        )
    return response


@router.post("/admin/products/{product_id}/template/import/confirm")
def product_import_confirm(
    request: Request,
    product_id: int,
    token: str = Form(...),
    accept: bool = Form(...),
    current_user: User = Depends(require_web_permission(PermissionCode.IMPORT_RUN)),
    import_service: ImportService = Depends(get_import_service),
):
    """Accept ('Add to Template & Import') or reject the new columns detected by a prior product import attempt."""
    temp_path = _PENDING_PRODUCT_IMPORTS.pop(token, None)
    context = base_context(request, current_user)

    if temp_path is None or not os.path.exists(temp_path):
        context.update({"product_id": product_id, "import_error": "This import has expired. Please re-upload the file."})
        response = templates.TemplateResponse("admin/_product_import_result.html", context)
        response.headers["HX-Trigger"] = hx_trigger("Import expired -- please re-upload.", "error")
        return response

    try:
        if not accept:
            result = None
            message, message_type = "Import rejected: new columns were not added.", "warning"
        else:
            result = import_service.import_setups_for_product(temp_path, product_id, current_user, accept_new_columns=True)
            message = "Import complete: {0} created, {1} updated. New column(s) added to the template.".format(
                result.created_count, result.updated_count
            )
            message_type = "success"
    except AppError as exc:
        result = None
        message, message_type = exc.message, "error"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    context.update({"product_id": product_id, "result": result})
    response = templates.TemplateResponse("admin/_product_import_result.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


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
        response.headers["HX-Trigger"] = hx_trigger(exc.message, "error")
        return response
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    context = base_context(request, current_user)
    context.update({"result": result})
    response = templates.TemplateResponse("admin/_setup_import_result.html", context)
    if result.committed:
        message = "Import complete: {0} created, {1} updated.".format(result.created_count, result.updated_count)
        response.headers["HX-Trigger"] = hx_trigger(message, "success")
    else:
        response.headers["HX-Trigger"] = hx_trigger(
            "Import rejected: {0} row error(s) found. No rows were committed.".format(result.error_count), "warning"
        )
    return response
