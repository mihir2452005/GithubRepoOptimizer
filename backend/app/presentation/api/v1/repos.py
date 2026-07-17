"""
Repository analysis endpoint — The main entry point for triggering analysis.
POST a repo URL, get back a full optimization report.
Supports both synchronous (wait for result) and async (background job) modes.
"""

import asyncio
import os
import uuid
import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from git import Repo, GitCommandError
import structlog

from ....agents.orchestrator import Orchestrator
from ....agents.shared_context import SharedAnalysisContextBuilder
from ....infrastructure.config.config_registry import get_config
from ....infrastructure.storage.history import get_history
from ...websocket.progress import send_progress, store_job_result, get_job_result, is_job_running, mark_job_running

logger = structlog.get_logger()

router = APIRouter(prefix="/repos", tags=["repos"])

# Check git availability at module level
GIT_AVAILABLE = shutil.which("git") is not None


class AnalyzeRequest(BaseModel):
    """Request body for repository analysis."""
    repo_url: str = Field(description="Git repository URL to analyze")
    github_token: str | None = Field(default=None, description="Optional GitHub token for private repos")
    async_mode: bool = Field(default=False, description="If true, return immediately with job_id and run in background")


class AnalyzeResponse(BaseModel):
    """Response containing full optimization report."""
    job_id: str
    status: str
    repo_url: str
    context: dict | None = None
    results: dict | None = None
    optimization_score: int | None = None
    health_grade: str | None = None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest):
    """
    Analyze a repository end-to-end:
    1. Clone the repo to workspace
    2. Build SharedAnalysisContext
    3. Run all agents in parallel via Orchestrator
    4. Return full optimization report

    If async_mode=true, returns immediately with job_id and status "running".
    Use GET /api/v1/jobs/{job_id}/status to poll or connect via WebSocket.
    """
    # Check git availability before attempting clone
    if not GIT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Git is not installed on this server. Please ensure the deployment environment has git available.",
        )

    config = get_config()
    job_id = str(uuid.uuid4())

    # Create workspace directory
    workspace_dir = os.path.abspath(config.workspace_dir)
    repo_dir = os.path.join(workspace_dir, job_id, "repo")
    os.makedirs(repo_dir, exist_ok=True)

    # Clone the repository
    try:
        clone_url = request.repo_url
        env_vars = {}

        if request.github_token:
            # Inject token for private repos
            if "github.com" in clone_url:
                clone_url = clone_url.replace(
                    "https://",
                    f"https://{request.github_token}@"
                )

        Repo.clone_from(
            clone_url,
            repo_dir,
            depth=1,  # Shallow clone for speed
            env=env_vars if env_vars else None,
        )
    except GitCommandError as e:
        # Cleanup on failure
        shutil.rmtree(os.path.join(workspace_dir, job_id), ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to clone repository: {str(e)}"
        )
    except Exception as e:
        shutil.rmtree(os.path.join(workspace_dir, job_id), ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during clone: {str(e)}"
        )

    # Async mode: return immediately and run in background
    if request.async_mode:
        asyncio.create_task(
            _run_analysis_background(job_id, repo_dir, request.repo_url)
        )
        return AnalyzeResponse(
            job_id=job_id,
            status="running",
            repo_url=request.repo_url,
        )

    # Synchronous mode: wait for the full analysis
    return await _run_analysis_sync(job_id, repo_dir, request.repo_url)


@router.get("/jobs/{job_id}/status", response_model=AnalyzeResponse)
async def get_job_status(job_id: str):
    """
    Poll the status of a background analysis job.
    Returns the full result if complete, or status "running" if still in progress.
    """
    result = get_job_result(job_id)
    if result is not None:
        return AnalyzeResponse(**result)

    if is_job_running(job_id):
        return AnalyzeResponse(
            job_id=job_id,
            status="running",
            repo_url="",
        )

    # Check history as fallback
    history = get_history()
    entry = history.get_by_id(job_id)
    if entry is not None:
        return AnalyzeResponse(
            job_id=entry["id"],
            status="completed",
            repo_url=entry["repo_url"],
            results=entry.get("full_results"),
            optimization_score=entry.get("optimization_score"),
            health_grade=entry.get("health_grade"),
        )

    raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")


async def _run_analysis_sync(job_id: str, repo_dir: str, repo_url: str) -> AnalyzeResponse:
    """Run analysis synchronously and return the response."""
    config = get_config()
    workspace_dir = os.path.abspath(config.workspace_dir)
    job_dir = os.path.join(workspace_dir, job_id)

    try:
        # Build shared analysis context
        context_builder = SharedAnalysisContextBuilder()
        context = context_builder.build(job_id=job_id, repo_path=repo_dir)

        # Run all agents in parallel
        orchestrator = Orchestrator()
        results = await orchestrator.run_analysis(
            job_id=job_id,
            repo_path=repo_dir,
            repo_url=repo_url,
        )

        # Serialize results
        serialized_results = {}
        for agent_name, output in results.items():
            serialized_results[agent_name] = output.model_dump()

        # Extract headline metrics
        optimization_score = None
        health_grade = None

        if "repository_optimization" in serialized_results:
            opt_metrics = serialized_results["repository_optimization"].get("metrics", {})
            optimization_score = opt_metrics.get("optimization_score")

        if "executive_cto" in serialized_results:
            exec_metrics = serialized_results["executive_cto"].get("metrics", {})
            health_grade = exec_metrics.get("health_grade")

        # Save to history
        try:
            history = get_history()
            history.save(job_id, repo_url, serialized_results,
                         optimization_score=optimization_score,
                         health_grade=health_grade,
                         context={
                             "total_files": len(context.file_index),
                             "languages": list(context.language_map.keys()),
                             "framework": context.framework_detection,
                         })
        except Exception as e:
            logger.warning("history_save_failed", job_id=job_id, error=str(e))

        return AnalyzeResponse(
            job_id=job_id,
            status="completed",
            repo_url=repo_url,
            context={
                "total_files": len(context.file_index),
                "languages": list(context.language_map.keys()),
                "framework": context.framework_detection,
            },
            results=serialized_results,
            optimization_score=optimization_score,
            health_grade=health_grade,
        )
    finally:
        # Cleanup workspace after analysis to conserve disk space (important on Render)
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.info("workspace_cleaned", job_id=job_id)


async def _run_analysis_background(job_id: str, repo_dir: str, repo_url: str) -> None:
    """Run analysis in the background with progress streaming."""
    config = get_config()
    workspace_dir = os.path.abspath(config.workspace_dir)
    job_dir = os.path.join(workspace_dir, job_id)

    try:
        # Build shared analysis context
        context_builder = SharedAnalysisContextBuilder()
        context = context_builder.build(job_id=job_id, repo_path=repo_dir)

        # Progress callback for WebSocket streaming
        async def on_progress(agent_name: str, status: str, completed: int, total: int):
            progress_pct = int((completed / total) * 100) if total > 0 else 0
            await send_progress(job_id, {
                "type": "agent_complete",
                "agent": agent_name,
                "status": status,
                "progress": progress_pct,
                "total_agents": total,
                "completed": completed,
            })

        # Run all agents in parallel with progress
        orchestrator = Orchestrator()
        results = await orchestrator.run_analysis(
            job_id=job_id,
            repo_path=repo_dir,
            repo_url=repo_url,
            progress_callback=on_progress,
        )

        # Serialize results
        serialized_results = {}
        for agent_name, output in results.items():
            serialized_results[agent_name] = output.model_dump()

        # Extract headline metrics
        optimization_score = None
        health_grade = None

        if "repository_optimization" in serialized_results:
            opt_metrics = serialized_results["repository_optimization"].get("metrics", {})
            optimization_score = opt_metrics.get("optimization_score")

        if "executive_cto" in serialized_results:
            exec_metrics = serialized_results["executive_cto"].get("metrics", {})
            health_grade = exec_metrics.get("health_grade")

        # Save to history
        try:
            history = get_history()
            history.save(job_id, repo_url, serialized_results,
                         optimization_score=optimization_score,
                         health_grade=health_grade,
                         context={
                             "total_files": len(context.file_index),
                             "languages": list(context.language_map.keys()),
                             "framework": context.framework_detection,
                         })
        except Exception as e:
            logger.warning("history_save_failed", job_id=job_id, error=str(e))

        # Store result for polling
        result_data = {
            "job_id": job_id,
            "status": "completed",
            "repo_url": repo_url,
            "context": {
                "total_files": len(context.file_index),
                "languages": list(context.language_map.keys()),
                "framework": context.framework_detection,
            },
            "results": serialized_results,
            "optimization_score": optimization_score,
            "health_grade": health_grade,
        }
        store_job_result(job_id, result_data)

        # Send completion message via WebSocket
        await send_progress(job_id, {
            "type": "complete",
            "job_id": job_id,
        })

    except Exception as e:
        logger.error("background_analysis_failed", job_id=job_id, error=str(e))
        error_result = {
            "job_id": job_id,
            "status": "error",
            "repo_url": repo_url,
            "error": str(e),
        }
        store_job_result(job_id, error_result)
        await send_progress(job_id, {
            "type": "error",
            "job_id": job_id,
            "error": str(e),
        })
    finally:
        # Cleanup workspace after analysis to conserve disk space (important on Render)
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.info("workspace_cleaned", job_id=job_id)
