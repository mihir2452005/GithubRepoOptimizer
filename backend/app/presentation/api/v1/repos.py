"""
Repository analysis endpoint — The main entry point for triggering analysis.
POST a repo URL, get back a full optimization report.
"""

import os
import uuid
import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from git import Repo, GitCommandError

from ....agents.orchestrator import Orchestrator
from ....agents.shared_context import SharedAnalysisContextBuilder
from ....infrastructure.config.config_registry import get_config

router = APIRouter(prefix="/repos", tags=["repos"])


class AnalyzeRequest(BaseModel):
    """Request body for repository analysis."""
    repo_url: str = Field(description="Git repository URL to analyze")
    github_token: str | None = Field(default=None, description="Optional GitHub token for private repos")


class AnalyzeResponse(BaseModel):
    """Response containing full optimization report."""
    job_id: str
    status: str
    repo_url: str
    context: dict
    results: dict
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
    """
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

    # Build shared analysis context
    context_builder = SharedAnalysisContextBuilder()
    context = context_builder.build(job_id=job_id, repo_path=repo_dir)

    # Run all agents in parallel
    orchestrator = Orchestrator()
    results = await orchestrator.run_analysis(
        job_id=job_id,
        repo_path=repo_dir,
        repo_url=request.repo_url,
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

    # Cleanup cloned repo (optional — could keep for caching)
    # shutil.rmtree(os.path.join(workspace_dir, job_id), ignore_errors=True)

    return AnalyzeResponse(
        job_id=job_id,
        status="completed",
        repo_url=request.repo_url,
        context={
            "total_files": len(context.file_index),
            "languages": list(context.language_map.keys()),
            "framework": context.framework_detection,
        },
        results=serialized_results,
        optimization_score=optimization_score,
        health_grade=health_grade,
    )
