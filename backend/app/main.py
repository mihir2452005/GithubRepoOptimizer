"""
FastAPI Application Factory — Entry point for the RepoGenius AI backend.
Lifespan hook validates config and discovers agents on startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from .infrastructure.config.config_registry import get_config
from .agents.registry import registry
from .presentation.api.v1.router import api_v1_router
from .presentation.api.v1.health import router as health_router
from .presentation.websocket.progress import router as ws_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    config = get_config()
    logger.info("config_validated", workspace=config.workspace_dir, environment=config.environment)

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
    config = get_config()

    app = FastAPI(
        title="RepoGenius AI",
        description="GitHub Repository Optimization Platform — AI-powered code analysis",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # Global exception handler — structured JSON errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("unhandled_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "detail": str(exc) if config.environment != "production" else "An internal error occurred",
                "path": str(request.url.path),
            },
        )

    # CORS middleware — allow all origins in development, configured origins in production
    # IMPORTANT: The CORS middleware MUST be added before routes to handle OPTIONS preflight
    allowed_origins_str = config.allowed_origins.strip() if config.allowed_origins else "*"
    
    if allowed_origins_str == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
    
    # Always allow common development origins
    if config.environment != "production":
        allowed_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(api_v1_router)
    app.include_router(health_router)  # Also at root /health for convenience
    app.include_router(ws_router)      # WebSocket progress streaming

    return app


# Module-level app instance for uvicorn
app = create_app()
