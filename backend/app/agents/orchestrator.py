"""
Orchestrator — Flat-parallel dispatch of all agents via asyncio.gather.
Never crashes the job — every agent failure is captured gracefully.
"""

import asyncio
import traceback

from .base import BaseAgent
from .payloads import AgentInputPayload, AgentOutputPayload
from .registry import registry
from ..infrastructure.config.config_registry import get_config


class Orchestrator:
    """
    Runs ALL discovered agents in parallel using asyncio.gather.
    Each agent is wrapped in asyncio.wait_for with a per-agent timeout.
    Failures are captured per-agent and never crash the job.
    """

    def __init__(self) -> None:
        self.config = get_config()

    async def run_analysis(
        self, job_id: str, repo_path: str, repo_url: str = ""
    ) -> dict[str, AgentOutputPayload]:
        """
        Execute all agents in parallel and return results.

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

        # Launch all agents in parallel
        tasks = [
            self._run_single_agent(agent, payload)
            for agent in agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        return {
            agents[i].name: results[i]
            for i in range(len(agents))
        }

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
