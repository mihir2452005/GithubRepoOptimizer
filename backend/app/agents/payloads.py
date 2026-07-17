"""
Agent Payload Models — Standardized input/output contracts for all agents.
Every agent receives AgentInputPayload and returns AgentOutputPayload.
"""

from typing import Literal
from pydantic import BaseModel, Field


class AgentInputPayload(BaseModel):
    """Standard input for every agent."""

    job_id: str = Field(description="Unique job identifier")
    repo_path: str = Field(description="Local filesystem path to cloned repo")
    repo_url: str = Field(default="", description="Original repository URL")
    metadata: dict = Field(
        default_factory=dict,
        description="Extra context (e.g., prior_results from other agents)",
    )


class AgentFinding(BaseModel):
    """A single finding produced by an agent — always includes a solution."""

    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        description="Finding severity level"
    )
    description: str = Field(description="Human-readable finding description")
    file_path: str | None = Field(default=None, description="Affected file path")
    line_number: int | None = Field(default=None, description="Affected line number")
    category: str = Field(default="general", description="Finding category")

    # Solution fields — every finding MUST have a fix suggestion
    solution: str = Field(
        default="",
        description="How to fix this issue — step-by-step explanation"
    )
    solution_code: str | None = Field(
        default=None,
        description="Code snippet showing the fix (before/after or new code)"
    )
    solution_reference: str | None = Field(
        default=None,
        description="URL or documentation reference for the fix"
    )

    # Security-specific fields
    owasp_category: str | None = Field(default=None, description="OWASP category if applicable")
    cwe_id: str | None = Field(default=None, description="CWE identifier if applicable")
    exploitability: Literal["high", "medium", "low", "none"] | None = Field(
        default=None, description="How exploitable is this finding"
    )
    fix_difficulty: Literal["easy", "medium", "hard"] | None = Field(
        default=None, description="Estimated difficulty to fix"
    )
    estimated_fix_minutes: int | None = Field(
        default=None, description="Estimated time to fix in minutes"
    )


class AgentOutputPayload(BaseModel):
    """Standard output from every agent."""

    agent: str = Field(description="Name of the agent that produced this output")
    status: Literal["success", "error", "timeout", "skipped"] = Field(
        description="Execution status"
    )
    findings: list[AgentFinding] = Field(
        default_factory=list, description="List of findings"
    )
    metrics: dict = Field(
        default_factory=dict, description="Agent-specific metrics"
    )
    summary: str = Field(default="", description="Human-readable summary")
    error_message: str | None = Field(
        default=None, description="Error message if status is error/timeout"
    )
    stack_trace: str | None = Field(
        default=None, description="Stack trace for debugging"
    )
