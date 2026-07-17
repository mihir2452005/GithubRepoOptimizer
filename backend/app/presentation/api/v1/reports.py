"""
Reports API — Generate and download HTML/JSON reports.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from ....infrastructure.storage.history import get_history
from ....application.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{job_id}/html", response_class=HTMLResponse)
async def get_html_report(job_id: str):
    """Download analysis results as a self-contained HTML report."""
    history = get_history()
    entry = history.get_by_id(job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Analysis not found")

    html = report_service.generate_html(
        job_id=job_id,
        repo_url=entry["repo_url"],
        results=entry.get("results", {}),
        optimization_score=entry.get("optimization_score"),
        health_grade=entry.get("health_grade"),
        context=entry.get("context"),
    )
    return HTMLResponse(content=html)


@router.get("/{job_id}/json")
async def get_json_report(job_id: str):
    """Download analysis results as raw JSON."""
    history = get_history()
    entry = history.get_by_id(job_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return JSONResponse(content=entry)
