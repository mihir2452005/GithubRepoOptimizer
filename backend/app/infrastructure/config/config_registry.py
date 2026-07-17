"""
Configuration Registry — Single source of truth for all application settings.
Uses Pydantic BaseSettings for env-driven configuration with validation.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class ConfigRegistry(BaseSettings):
    """Centralized configuration singleton loaded from environment variables."""

    # Deployment environment
    environment: str = Field(
        default="development",
        description="Deployment environment: development, staging, production",
    )

    # CORS allowed origins (comma-separated)
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins. Use * for all.",
    )

    # Request timeout
    request_timeout_seconds: int = Field(
        default=120,
        description="Max seconds for clone + analysis requests",
    )

    # Core infrastructure
    database_url: str = Field(
        default="sqlite+aiosqlite:///./repogenius.db",
        description="Async database connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="JWT signing secret",
    )

    # AI provider settings
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )
    ai_provider_order: list[str] = Field(
        default=["ollama"],
        description="Ordered list of AI providers to try",
    )

    # Orchestrator settings
    orchestrator_concurrency: int = Field(
        default=10,
        description="Max concurrent agent executions",
    )
    agent_timeout_seconds: int = Field(
        default=60,
        description="Default timeout per agent in seconds",
    )

    # Feature flags
    enable_kg: bool = Field(default=False, description="Enable Knowledge Graph")
    enable_optimization: bool = Field(default=True, description="Enable optimization agent")
    enable_security: bool = Field(default=True, description="Enable security agent")
    enable_code_quality: bool = Field(default=True, description="Enable code quality agent")
    enable_architecture: bool = Field(default=True, description="Enable architecture agent")
    enable_dependency: bool = Field(default=True, description="Enable dependency agent")
    enable_technical_debt: bool = Field(default=True, description="Enable technical debt agent")

    # Workspace settings
    workspace_dir: str = Field(
        default="./workspace",
        description="Directory for cloned repositories",
    )

    # Agent-specific timeout overrides
    agent_timeouts: dict[str, int] = Field(
        default_factory=dict,
        description="Per-agent timeout overrides: {agent_name: seconds}",
    )

    def get_agent_timeout(self, agent_name: str) -> int:
        """Get timeout for a specific agent, falling back to default."""
        return self.agent_timeouts.get(agent_name, self.agent_timeout_seconds)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_config() -> ConfigRegistry:
    """Get cached configuration singleton."""
    return ConfigRegistry()
