"""
BaseAgent — Abstract base class for all agents in the system.
Drop a new agent file in agents/core/ and it auto-discovers.
"""

from abc import ABC, abstractmethod

from .payloads import AgentInputPayload, AgentOutputPayload


class BaseAgent(ABC):
    """
    Abstract base for every analysis agent.

    Subclass contract:
    - Set `name` (unique identifier)
    - Set `version` (semver string)
    - Set `dependencies` (list of agent names that must run first, empty for parallel)
    - Implement `run(payload) -> AgentOutputPayload`
    """

    name: str = "unnamed_agent"
    version: str = "1.0.0"
    dependencies: list[str] = []

    @abstractmethod
    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        """Execute the agent's analysis. Must be implemented by subclasses."""
        ...

    async def pre_run(self, payload: AgentInputPayload) -> None:
        """Hook called before run(). Override for setup logic."""
        pass

    async def post_run(self, payload: AgentInputPayload, output: AgentOutputPayload) -> None:
        """Hook called after run(). Override for cleanup/logging."""
        pass

    async def on_error(self, payload: AgentInputPayload, error: Exception) -> None:
        """Hook called when run() raises. Override for error handling."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} v{self.version}>"
