"""
Orchestrator — Flat-parallel dispatch of all agents via asyncio.gather.
Never crashes the job — every agent failure is captured gracefully.
Supports progress_callback for real-time streaming updates.
"""

import asyncio
import traceback
from typing import Callable, Awaitable

from .base import BaseAgent
from .payloads import AgentInputPayload, AgentOutputPayload
from .registry import registry
from ..infrastructure.config.config_registry import get_config

# Type alias for the progress callback
ProgressCallback = Callable[[str, str, int, int], Awaitable[None]]


class Orchestrator:
    """
    Runs ALL discovered agents in parallel using asyncio.gather.
    Each agent is wrapped in asyncio.wait_for with a per-agent timeout.
    Failures are captured per-agent and never crash the job.
    """

    def __init__(self) -> None:
        self.config = get_config()

    async def run_analysis(
        self,
        job_id: str,
        repo_path: str,
        repo_url: str = "",
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, AgentOutputPayload]:
        """
        Execute all agents in parallel and return results.

        Args:
            job_id: Unique job identifier
            repo_path: Local filesystem path to cloned repo
            repo_url: Original repository URL
            progress_callback: Optional async callback called after each agent completes.
                Signature: (agent_name, status, completed_count, total_count) -> None

        Returns:
            dict mapping agent_name -> AgentOutputPayload
        """
        agents = registry.get_all()
        if not agents:
            return {}

        payload = AgentInputPayload(
            job_id=job_id,
            repo_path=repo_path,
            repo_url=repo_url,
        )

        total_agents = len(agents)
        completed_count = 0
        results_dict: dict[str, AgentOutputPayload] = {}
        lock = asyncio.Lock()

        async def run_with_progress(agent: BaseAgent) -> tuple[str, AgentOutputPayload]:
            nonlocal completed_count
            output = await self._run_single_agent(agent, payload)

            async with lock:
                completed_count += 1
                current_completed = completed_count

            if progress_callback:
                try:
                    await progress_callback(
                        agent.name, output.status, current_completed, total_agents
                    )
                except Exception:
                    pass  # Never let callback errors crash the job

            return (agent.name, output)

        # Launch all agents in parallel
        tasks = [run_with_progress(agent) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return {name: output for name, output in results}

    async def _run_single_agent(
        self, agent: BaseAgent, payload: AgentInputPayload
    ) -> AgentOutputPayload:
        """Run a single agent with timeout and error handling."""
        timeout = self.config.get_agent_timeout(agent.name)

        try:
            await agent.pre_run(payload)
            output = await asyncio.wait_for(
                agent.run(payload),
                timeout=timeout,
            )
            await agent.post_run(payload, output)
            return output

        except asyncio.TimeoutError:
            return AgentOutputPayload(
                agent=agent.name,
                status="timeout",
                error_message=f"Agent '{agent.name}' timed out after {timeout}s",
            )

        except Exception as e:
            await agent.on_error(payload, e)
            return AgentOutputPayload(
                agent=agent.name,
                status="error",
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )
