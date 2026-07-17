"""
Health check endpoint — Quick status check for load balancers and monitoring.
Reports service health, git availability, and workspace status.
"""

import os
import shutil

from fastapi import APIRouter
import structlog

from ....agents.registry import registry
from ....infrastructure.config.config_registry import get_config

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

# Check git availability at module load
GIT_AVAILABLE = shutil.which("git") is not None


@router.get("/health")
async def health_check():
    """
    Returns service health status, registered agent count,
    git availability, environment, and workspace writability.
    Used by load balancers and monitoring systems.
    """
    config = get_config()
    agents = registry.get_all()

    # Check if workspace directory is writable
    workspace_writable = False
    try:
        workspace_dir = os.path.abspath(config.workspace_dir)
        os.makedirs(workspace_dir, exist_ok=True)
        test_file = os.path.join(workspace_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        workspace_writable = True
    except (OSError, IOError) as e:
        logger.warning("workspace_not_writable", error=str(e))

    return {
        "status": "ok",
        "environment": config.environment,
        "git_available": GIT_AVAILABLE,
        "workspace_writable": workspace_writable,
        "agents": len(agents),
        "agent_names": [a.name for a in agents],
    }
