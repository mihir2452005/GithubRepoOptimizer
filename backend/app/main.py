"""
FastAPI Application Factory — Entry point for the RepoGenius AI backend.
Lifespan hook validates config and discovers agents on startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from .infrastructure.config.config_registry import get_config
from .agents.registry import registry
from .presentation.api.v1.router import api_v1_router
from .presentation.api.v1.health import router as health_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    config = get_config()
    logger.info("config_validated", workspace=config.workspace_dir)

    # Discover all agents
    registry.discover(package="app.agents")
    agents = registry.get_all()
    logger.info(
        "agents_discovered",
        count=len(agents),
        names=[a.name for a in agents],
    )

    yield

    # Shutdown
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="RepoGenius AI",
        description="GitHub Repository Optimization Platform — AI-powered code analysis",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(api_v1_router)
    app.include_router(health_router)  # Also at root /health for convenience

    return app


# Module-level app instance for uvicorn
app = create_app()
