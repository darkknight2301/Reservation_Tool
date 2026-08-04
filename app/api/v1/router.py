"""Aggregates every v1 API router under a single ``APIRouter``."""
from fastapi import APIRouter

from app.api.v1 import (
    announcements,
    audit,
    auth,
    exports,
    groups,
    imports,
    products,
    reservations,
    setups,
    swaps,
    users,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(groups.router)
api_router.include_router(setups.router)
api_router.include_router(reservations.router)
api_router.include_router(swaps.router)
api_router.include_router(announcements.router)
api_router.include_router(audit.router)
api_router.include_router(exports.router)
api_router.include_router(imports.router)
