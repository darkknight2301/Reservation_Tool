"""
Reservation table screen and the Reserve / Swap / Unreserve dialogs.

The table is server-rendered and re-fetched via HTMX on filter/search/page
changes. Since ``reserved_by`` and ``reserved_time`` are facts about the
*Reservation* aggregate (not the Setup itself -- see the architecture
document, section 4.3), this router joins the paginated Setup page against
every currently-ACTIVE reservation to build each row.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.deps import (
    get_export_service,
    get_group_service,
    get_product_service,
    get_reservation_service,
    get_setup_service,
    get_swap_service,
    get_template_service,
    get_user_service,
)
from app.core.constants import AnnouncementChannel, PermissionCode, ReservationStatus, SetupStatus, UserStatus
from app.core.exceptions import AppError
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationFilter
from app.schemas.setup import SetupFilter, SetupUpdateRequest
from app.schemas.swap_request import SwapCreateRequest
from app.schemas.user import UserFilter
from app.services.export_service import ExportService
from app.services.group_service import GroupService
from app.services.product_service import ProductService
from app.services.reservation_service import ReservationService
from app.services.setup_service import SetupService
from app.services.swap_service import SwapService
from app.services.template_service import TemplateService
from app.services.user_service import UserService
from app.utils.pagination import total_pages as compute_total_pages
from app.web.deps import base_context, get_current_web_user, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(tags=["Web - Setups"])


def _build_rows(
    setups: List,
    current_user: User,
    reservation_service: ReservationService,
    custom_values_by_setup: Optional[Dict[int, Dict]] = None,
) -> List[Dict]:
    """Join a page of Setups against active Reservations to build display rows."""
    active_reservations: List[Reservation] = reservation_service.list_all(ReservationFilter(status=ReservationStatus.ACTIVE))
    reservation_by_setup_id = {r.setup_id: r for r in active_reservations}
    custom_values_by_setup = custom_values_by_setup or {}

    rows = []
    for setup in setups:
        reservation = reservation_by_setup_id.get(setup.id)
        is_mine = reservation is not None and reservation.user_id == current_user.id
        rows.append(
            {
                "setup": setup,
                "reservation": reservation,
                "is_mine": is_mine,
                "checkbox_enabled": setup.status == SetupStatus.AVAILABLE or is_mine,
                "custom_values": custom_values_by_setup.get(setup.id, {}),
            }
        )
    return rows


def _load_table_context(
    request: Request,
    filters: SetupFilter,
    page: int,
    page_size: int,
    current_user: User,
    setup_service: SetupService,
    reservation_service: ReservationService,
    template_service: Optional[TemplateService] = None,
) -> dict:
    setups, total_items = setup_service.list(filters, page, page_size)

    # The table only renders a single product's custom columns when the view
    # is scoped to exactly one Product (its template is otherwise ambiguous
    # across products with different columns) -- see "Dynamic Frontend Table".
    custom_columns = []
    custom_values_by_setup: Dict[int, Dict] = {}
    if template_service is not None and filters.product_id is not None:
        custom_columns = template_service.get_custom_columns(filters.product_id)
        if setups:
            custom_values_by_setup = template_service.get_values_map_for_setups(
                [s.id for s in setups], filters.product_id
            )

    rows = _build_rows(setups, current_user, reservation_service, custom_values_by_setup)
    context = base_context(request, current_user)
    context.update(
        {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": compute_total_pages(total_items, page_size),
            "filters": filters,
            "custom_columns": custom_columns,
        }
    )
    return context


@router.get("/setups")
def setups_page(
    request: Request,
    product_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_web_user),
    setup_service: SetupService = Depends(get_setup_service),
    reservation_service: ReservationService = Depends(get_reservation_service),
    product_service: ProductService = Depends(get_product_service),
    group_service: GroupService = Depends(get_group_service),
    template_service: TemplateService = Depends(get_template_service),
):
    """Render the full reservation table screen (initial page load)."""
    filters = SetupFilter(product_id=product_id, group_id=group_id, status=status, location=location, search=search)
    context = _load_table_context(
        request, filters, page, page_size, current_user, setup_service, reservation_service, template_service
    )
    products, _ = product_service.list(page=1, page_size=200)
    groups, _ = group_service.list(page=1, page_size=200)
    context.update({"products": products, "groups": groups})
    return templates.TemplateResponse("setups/table.html", context)


@router.get("/setups/table")
def setups_table_partial(
    request: Request,
    product_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_web_user),
    setup_service: SetupService = Depends(get_setup_service),
    reservation_service: ReservationService = Depends(get_reservation_service),
    template_service: TemplateService = Depends(get_template_service),
):
    """HTMX partial: re-render just the table body + pagination on filter/search/page change."""
    filters = SetupFilter(product_id=product_id, group_id=group_id, status=status, location=location, search=search)
    context = _load_table_context(
        request, filters, page, page_size, current_user, setup_service, reservation_service, template_service
    )
    return templates.TemplateResponse("setups/_table_body.html", context)


@router.get("/setups/reserve-dialog")
def reserve_dialog(
    request: Request,
    setup_ids: str,
    current_user: User = Depends(require_web_permission(PermissionCode.RESERVATION_CREATE)),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Render the Reserve dialog for one or more selected AVAILABLE setups."""
    ids = [int(value) for value in setup_ids.split(",") if value]
    setups = [setup_service.get_by_id(setup_id) for setup_id in ids]
    context = base_context(request, current_user)
    context.update({"setups": setups, "setup_ids": setup_ids, "announcement_channels": AnnouncementChannel.ALL})
    return templates.TemplateResponse("setups/reserve_dialog.html", context)


@router.post("/setups/reserve")
def reserve_submit(
    request: Request,
    setup_ids: str = Form(...),
    reserved_from: str = Form(...),
    reserved_until: str = Form(...),
    remarks: str = Form(default=""),
    announcement_channels: List[str] = Form(default=[]),
    announcement_message: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.RESERVATION_CREATE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Create a reservation for every selected setup over the same time window, with optional announcement broadcast."""
    ids = [int(value) for value in setup_ids.split(",") if value]
    reserved_from_dt = datetime.fromisoformat(reserved_from)
    reserved_until_dt = datetime.fromisoformat(reserved_until)

    errors = []
    for setup_id in ids:
        try:
            payload = ReservationCreateRequest(
                setup_id=setup_id,
                reserved_from=reserved_from_dt,
                reserved_until=reserved_until_dt,
                remarks=remarks or None,
                announcement_channels=announcement_channels,
                announcement_message=announcement_message or None,
            )
            reservation_service.create(payload, current_user)
        except AppError as exc:
            errors.append("Setup {0}: {1}".format(setup_id, exc.message))

    filters = SetupFilter()
    context = _load_table_context(request, filters, 1, 25, current_user, setup_service, reservation_service)
    response = templates.TemplateResponse("setups/_table_body.html", context)

    if errors:
        response.headers["HX-Trigger"] = hx_trigger("; ".join(errors), "warning", close_dialog=False)
    else:
        response.headers["HX-Trigger"] = hx_trigger("Reservation created successfully.", "success", close_dialog=True)
    return response


@router.get("/setups/swap-dialog")
def swap_dialog(
    request: Request,
    reservation_id: int,
    current_user: User = Depends(get_current_web_user),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Render the Swap dialog: pick a replacement AVAILABLE setup of the same product."""
    reservation = reservation_service.get_by_id(reservation_id)
    current_setup = setup_service.get_by_id(reservation.setup_id)
    candidate_setups, _ = setup_service.list(
        SetupFilter(product_id=current_setup.product_id, status=SetupStatus.AVAILABLE), page=1, page_size=200
    )
    candidate_setups = [s for s in candidate_setups if s.id != current_setup.id]

    context = base_context(request, current_user)
    context.update({"reservation": reservation, "current_setup": current_setup, "candidate_setups": candidate_setups})
    return templates.TemplateResponse("setups/swap_dialog.html", context)


@router.post("/setups/swap")
def swap_submit(
    request: Request,
    reservation_id: int = Form(...),
    requested_setup_id: int = Form(...),
    reason: str = Form(default=""),
    current_user: User = Depends(get_current_web_user),
    swap_service: SwapService = Depends(get_swap_service),
    setup_service: SetupService = Depends(get_setup_service),
    reservation_service: ReservationService = Depends(get_reservation_service),
):
    """Submit a swap request for approval."""
    message, message_type = "Swap request submitted for approval.", "success"
    try:
        payload = SwapCreateRequest(reservation_id=reservation_id, requested_setup_id=requested_setup_id, reason=reason or None)
        swap_service.create(payload, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    filters = SetupFilter()
    context = _load_table_context(request, filters, 1, 25, current_user, setup_service, reservation_service)
    response = templates.TemplateResponse("setups/_table_body.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=(message_type == "success"))
    return response


@router.get("/setups/unreserve-dialog")
def unreserve_dialog(
    request: Request,
    reservation_ids: str,
    current_user: User = Depends(get_current_web_user),
    reservation_service: ReservationService = Depends(get_reservation_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Render the Unreserve confirmation dialog, warning if a swap is still pending on any selection."""
    ids = [int(value) for value in reservation_ids.split(",") if value]
    reservations = [reservation_service.get_by_id(reservation_id) for reservation_id in ids]
    blocked_reservation_ids = {
        reservation.id for reservation in reservations if swap_service.get_pending_for_reservation(reservation.id) is not None
    }
    context = base_context(request, current_user)
    context.update(
        {
            "reservations": reservations,
            "reservation_ids": reservation_ids,
            "blocked_reservation_ids": blocked_reservation_ids,
        }
    )
    return templates.TemplateResponse("setups/unreserve_dialog.html", context)


@router.post("/setups/unreserve")
def unreserve_submit(
    request: Request,
    reservation_ids: str = Form(...),
    current_user: User = Depends(get_current_web_user),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
):
    """Cancel (unreserve) every selected reservation."""
    ids = [int(value) for value in reservation_ids.split(",") if value]
    errors = []
    for reservation_id in ids:
        try:
            reservation_service.cancel(reservation_id, current_user)
        except AppError as exc:
            errors.append("Reservation {0}: {1}".format(reservation_id, exc.message))

    filters = SetupFilter()
    context = _load_table_context(request, filters, 1, 25, current_user, setup_service, reservation_service)
    response = templates.TemplateResponse("setups/_table_body.html", context)
    if errors:
        response.headers["HX-Trigger"] = hx_trigger("; ".join(errors), "warning", close_dialog=False)
    else:
        response.headers["HX-Trigger"] = hx_trigger("Setup(s) unreserved successfully.", "success", close_dialog=True)
    return response


@router.get("/setups/export")
def export_setups_web(
    product_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_web_permission(PermissionCode.EXPORT_RUN)),
    export_service: ExportService = Depends(get_export_service),
):
    """Export the current Setup filter view to Excel (cookie-authed browser download)."""
    filters = SetupFilter(product_id=product_id, group_id=group_id, status=status, location=location, search=search)
    export_log = export_service.export_setups(filters, current_user)
    return FileResponse(
        path=export_log.file_path,
        filename=export_log.file_path.split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/setups/{setup_id}/edit-form")
def setup_edit_form(
    request: Request,
    setup_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
    group_service: GroupService = Depends(get_group_service),
    user_service: UserService = Depends(get_user_service),
    template_service: TemplateService = Depends(get_template_service),
):
    """Render the Edit Setup modal, including this setup's product-specific custom fields."""
    setup = setup_service.get_by_id(setup_id)
    groups, _ = group_service.list(page=1, page_size=200)
    owners, _ = user_service.list(UserFilter(status=UserStatus.APPROVED), page=1, page_size=500)
    custom_columns = template_service.get_custom_columns(setup.product_id)
    custom_values = template_service.get_values_map_for_setup(setup_id, setup.product_id) if custom_columns else {}

    context = base_context(request, current_user)
    context.update(
        {
            "setup": setup, "groups": groups, "owners": owners, "statuses": SetupStatus.ALL,
            "custom_columns": custom_columns, "custom_values": custom_values,
        }
    )
    return templates.TemplateResponse("setups/_setup_edit_modal.html", context)


@router.post("/setups/{setup_id}/save")
async def setup_edit_save(
    request: Request,
    setup_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.PRODUCT_MANAGE)),
    setup_service: SetupService = Depends(get_setup_service),
    reservation_service: ReservationService = Depends(get_reservation_service),
    template_service: TemplateService = Depends(get_template_service),
):
    """Update a Setup's fields (and its product's custom template field values), then re-render the table."""
    form = await request.form()
    message, message_type = "Setup updated successfully.", "success"
    try:
        setup = setup_service.get_by_id(setup_id)
        payload = SetupUpdateRequest(
            group_id=int(form["group_id"]) if form.get("group_id") else None,
            owner_id=int(form["owner_id"]) if form.get("owner_id") else None,
            ip_address=form.get("ip_address") or None,
            hostname=form.get("hostname") or None,
            ssd=form.get("ssd") or None,
            hdd=form.get("hdd") or None,
            hardware_info=form.get("hardware_info") or None,
            capacity=form.get("capacity") or None,
            form_factor=form.get("form_factor") or None,
            adapter=form.get("adapter") or None,
            aardvark=form.get("aardvark") or None,
            quarch=form.get("quarch") or None,
            apc=form.get("apc") or None,
            remote_server=form.get("remote_server") or None,
            location=form.get("location") or None,
            remarks=form.get("remarks") or None,
            status=form.get("status") or None,
        )
        setup_service.update(setup_id, payload, current_user)

        custom_columns = template_service.get_custom_columns(setup.product_id)
        if custom_columns:
            raw_values: Dict[str, object] = {}
            for column in custom_columns:
                field_name = "custom_" + column.name
                if field_name in form:
                    if column.data_type == "BOOLEAN":
                        raw_values[column.name] = field_name in form  # checkbox present == checked
                    else:
                        raw_values[column.name] = form.get(field_name)
            if raw_values:
                template_service.set_setup_values(setup_id, setup.product_id, raw_values, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"
    except ValidationError as exc:
        message, message_type = "; ".join(err["msg"] for err in exc.errors()), "error"
    except (ValueError, KeyError) as exc:
        message, message_type = str(exc), "error"

    filters = SetupFilter()
    context = _load_table_context(request, filters, 1, 25, current_user, setup_service, reservation_service)
    response = templates.TemplateResponse("setups/_table_body.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type, close_dialog=(message_type == "success"))
    return response
