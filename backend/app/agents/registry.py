"""
AgentRegistry — Auto-discovers all agents via pkgutil package walking.
Drop a new agent file in agents/core/ and it's automatically available.
"""

import importlib
import pkgutil
import inspect
from typing import Type

from .base import BaseAgent


class AgentRegistry:
    """Discovers and manages all registered agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._discovered: bool = False

    def discover(self, package: str = "app.agents") -> None:
        """
        Walk through the agents package and register all BaseAgent subclasses.
        This enables the plugin system — just drop a file, it auto-discovers.
        """
        try:
            pkg = importlib.import_module(package)
        except ImportError:
            return

        if not hasattr(pkg, "__path__"):
            return

        for _importer, module_name, is_pkg in pkgutil.walk_packages(
            pkg.__path__, prefix=f"{package}."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseAgent)
                    and obj is not BaseAgent
                    and not inspect.isabstract(obj)
                ):
                    self.register(obj)

        self._discovered = True

    def register(self, agent_class: Type[BaseAgent]) -> None:
        """Register a single agent class."""
        instance = agent_class()
        self._agents[instance.name] = instance

    def get_all(self) -> list[BaseAgent]:
        """Return all registered agent instances."""
        if not self._discovered:
            self.discover()
        return list(self._agents.values())

    def get_agent(self, name: str) -> BaseAgent | None:
        """Get a specific agent by name."""
        if not self._discovered:
            self.discover()
        return self._agents.get(name)

    @property
    def count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)


# Module-level singleton
registry = AgentRegistry()
