"""
API v1 Router — Aggregates all sub-routers for the v1 API surface.
"""

from fastapi import APIRouter

from .health import router as health_router
from .repos import router as repos_router
from .history import router as history_router
from .diff import router as diff_router
from .reports import router as reports_router

api_v1_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_v1_router.include_router(health_router)
api_v1_router.include_router(repos_router)
api_v1_router.include_router(history_router)
api_v1_router.include_router(diff_router)
api_v1_router.include_router(reports_router)
