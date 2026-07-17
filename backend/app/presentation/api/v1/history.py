"""
History API — View past analyses and compare runs.
"""

from fastapi import APIRouter, HTTPException, Query

from ....infrastructure.storage.history import history_store

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
async def list_history():
    """List all past analyses (most recent first)."""
    return history_store.get_all()


@router.get("/{job_id}")
async def get_analysis(job_id: str):
    """Get full results for a past analysis."""
    entry = history_store.get_by_id(job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return entry


@router.get("/repo/search")
async def get_repo_history(url: str = Query(..., description="Repository URL")):
    """Get all analyses for a specific repository."""
    results = history_store.get_by_repo(url)
    return results
