"""
Swap Mapping screen: lets a Lead+ coordinate a multi-node swap mapping
(A->B, B->A, C->D) across several users' reservations in one atomic action.
"""
from typing import List

from fastapi import APIRouter, Depends, Form, Request

from app.api.deps import get_reservation_service, get_setup_service, get_swap_service
from app.core.constants import PermissionCode, ReservationStatus, SwapStatus
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.reservation import ReservationFilter
from app.schemas.setup import SetupFilter
from app.schemas.swap_request import SwapDecisionRequest, SwapFilter, SwapMappingCreateRequest, SwapMappingEntry
from app.services.reservation_service import ReservationService
from app.services.setup_service import SetupService
from app.services.swap_service import SwapService
from app.web.deps import base_context, require_web_permission, templates
from app.web.htmx_utils import hx_trigger

router = APIRouter(tags=["Web - Swap Mapping"])


def _load_page_context(
    request: Request,
    current_user: User,
    reservation_service: ReservationService,
    setup_service: SetupService,
    swap_service: SwapService,
) -> dict:
    active_reservations, _ = reservation_service.list(ReservationFilter(status=ReservationStatus.ACTIVE), page=1, page_size=500)
    all_setups, _ = setup_service.list(SetupFilter(), page=1, page_size=1000)
    pending_swaps, _ = swap_service.list(SwapFilter(status=SwapStatus.PENDING), page=1, page_size=500)

    # Two distinct pending-approval flows share this screen: coordinated
    # multi-node mappings (grouped by batch_id) and individual column-swap
    # requests submitted from the Swap dialog (batch_id is None for those).
    batches = {}
    single_swaps = []
    for swap in pending_swaps:
        if swap.batch_id:
            batches.setdefault(swap.batch_id, []).append(swap)
        else:
            single_swaps.append(swap)

    context = base_context(request, current_user)
    context.update({
        "active_reservations": active_reservations, "all_setups": all_setups,
        "batches": batches, "single_swaps": single_swaps,
    })
    return context


@router.get("/admin/swap-mapping")
def swap_mapping_page(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Render the Swap Mapping builder + pending-batches list."""
    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    return templates.TemplateResponse("admin/swap_mapping.html", context)


@router.get("/admin/swap-mapping/batches")
def swap_mapping_batches_partial(
    request: Request,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """HTMX partial: re-render the pending swap-mapping batches list."""
    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    return templates.TemplateResponse("admin/_swap_mapping_batches.html", context)


@router.post("/admin/swap-mapping/create")
def create_swap_mapping_web(
    request: Request,
    reservation_ids: List[int] = Form(...),
    target_setup_ids: List[int] = Form(...),
    reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Validate and create a swap mapping from paired reservation/target-setup form rows."""
    message, message_type = "Swap mapping created and pending approval.", "success"
    if len(reservation_ids) != len(target_setup_ids) or len(reservation_ids) < 2:
        message, message_type = "A mapping requires at least two matched reservation/target rows.", "error"
    else:
        mappings = [
            SwapMappingEntry(reservation_id=r_id, target_setup_id=s_id)
            for r_id, s_id in zip(reservation_ids, target_setup_ids)
        ]
        try:
            swap_service.create_mapping(SwapMappingCreateRequest(mappings=mappings, reason=reason or None), current_user)
        except AppError as exc:
            message, message_type = exc.message, "error"

    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    response = templates.TemplateResponse("admin/_swap_mapping_batches.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/admin/swap-mapping/{batch_id}/approve")
def approve_swap_mapping_web(
    request: Request,
    batch_id: str,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Approve every swap request in a mapping batch atomically."""
    message, message_type = "Swap mapping approved successfully.", "success"
    try:
        swap_service.approve_mapping(batch_id, current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    response = templates.TemplateResponse("admin/_swap_mapping_batches.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/admin/swap-mapping/single/{swap_id}/approve")
def approve_single_swap_web(
    request: Request,
    swap_id: int,
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Approve an individual (non-mapping) column-swap request submitted from the Swap dialog."""
    message, message_type = "Swap request approved -- values exchanged.", "success"
    try:
        swap_service.approve(swap_id, SwapDecisionRequest(), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    response = templates.TemplateResponse("admin/_swap_mapping_batches.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response


@router.post("/admin/swap-mapping/single/{swap_id}/reject")
def reject_single_swap_web(
    request: Request,
    swap_id: int,
    reason: str = Form(default=""),
    current_user: User = Depends(require_web_permission(PermissionCode.SWAP_APPROVE)),
    reservation_service: ReservationService = Depends(get_reservation_service),
    setup_service: SetupService = Depends(get_setup_service),
    swap_service: SwapService = Depends(get_swap_service),
):
    """Reject an individual (non-mapping) column-swap request."""
    message, message_type = "Swap request rejected.", "success"
    try:
        swap_service.reject(swap_id, SwapDecisionRequest(reason=reason or None), current_user)
    except AppError as exc:
        message, message_type = exc.message, "error"

    context = _load_page_context(request, current_user, reservation_service, setup_service, swap_service)
    response = templates.TemplateResponse("admin/_swap_mapping_batches.html", context)
    response.headers["HX-Trigger"] = hx_trigger(message, message_type)
    return response
