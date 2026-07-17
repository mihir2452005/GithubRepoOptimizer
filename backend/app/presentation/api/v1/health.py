"""
Health check endpoint — Quick status check for load balancers and monitoring.
"""

from fastapi import APIRouter

from ....agents.registry import registry

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Returns service health status and registered agent count.
    Used by load balancers and monitoring systems.
    """
    agents = registry.get_all()
    return {
        "status": "ok",
        "agents": len(agents),
        "agent_names": [a.name for a in agents],
    }
