"""
Diff API — Compare two analysis runs.
"""

from fastapi import APIRouter, Query

from ....application.services.diff_service import diff_service

router = APIRouter(prefix="/diff", tags=["diff"])


@router.get("")
async def compare_analyses(
    job_a: str = Query(..., description="ID of the older analysis"),
    job_b: str = Query(..., description="ID of the newer analysis"),
):
    """Compare two analysis runs and show what changed."""
    return diff_service.compare(job_a, job_b)
