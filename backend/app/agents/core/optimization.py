"""
RepositoryOptimizationAgent — Merges findings, computes optimization score,
generates Quick Wins and Sprint Roadmap.
"""

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class RepositoryOptimizationAgent(BaseAgent):
    name = "repository_optimization"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        prior_results: dict = payload.metadata.get("prior_results", {})
        findings: list[AgentFinding] = []

        # Collect all findings from prior results
        all_findings: list[dict] = []
        for agent_name, result in prior_results.items():
            if isinstance(result, dict):
                for f in result.get("findings", []):
                    if isinstance(f, dict):
                        f["source_agent"] = agent_name
                        all_findings.append(f)

        # Deduplicate findings by description + file_path
        seen: set[str] = set()
        unique_findings: list[dict] = []
        for f in all_findings:
            key = f"{f.get('description', '')}|{f.get('file_path', '')}"
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        # Count by severity
        critical_count = sum(1 for f in unique_findings if f.get("severity") == "critical")
        high_count = sum(1 for f in unique_findings if f.get("severity") == "high")
        medium_count = sum(1 for f in unique_findings if f.get("severity") == "medium")
        low_count = sum(1 for f in unique_findings if f.get("severity") == "low")

        # Compute Optimization Score: max(0, 100 - critical*5 - high*2)
        optimization_score = max(0, 100 - (critical_count * 5) - (high_count * 2))

        # Generate Quick Wins (easy fixes with high impact)
        quick_wins = self._generate_quick_wins(unique_findings)

        # Generate Sprint Roadmap
        sprint_roadmap = self._generate_sprint_roadmap(unique_findings)

        # Priority-ordered findings for the report
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        unique_findings.sort(key=lambda f: priority_order.get(f.get("severity", "info"), 4))

        findings.append(AgentFinding(
            severity="info",
            description=f"Optimization Score: {optimization_score}/100",
            category="optimization_score",
        ))

        summary = (
            f"Optimization Score: {optimization_score}/100. "
            f"Total unique findings: {len(unique_findings)} "
            f"(Critical: {critical_count}, High: {high_count}, "
            f"Medium: {medium_count}, Low: {low_count}). "
            f"Quick wins identified: {len(quick_wins)}."
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "optimization_score": optimization_score,
                "total_findings": len(unique_findings),
                "severity_breakdown": {
                    "critical": critical_count,
                    "high": high_count,
                    "medium": medium_count,
                    "low": low_count,
                },
                "quick_wins": quick_wins,
                "sprint_roadmap": sprint_roadmap,
                "prioritized_findings": unique_findings[:20],  # Top 20
            },
            summary=summary,
        )

    def _generate_quick_wins(self, findings: list[dict]) -> list[dict]:
        """Identify easy fixes with high impact."""
        quick_wins = []

        for f in findings:
            fix_difficulty = f.get("fix_difficulty", "medium")
            severity = f.get("severity", "low")
            estimated_minutes = f.get("estimated_fix_minutes", 30)

            # Quick win = easy fix + high/critical severity, or any easy fix under 15 min
            if fix_difficulty == "easy" and severity in ("critical", "high"):
                quick_wins.append({
                    "description": f.get("description", ""),
                    "file_path": f.get("file_path"),
                    "severity": severity,
                    "estimated_minutes": estimated_minutes,
                    "impact": "high",
                })
            elif fix_difficulty == "easy" and estimated_minutes and estimated_minutes <= 15:
                quick_wins.append({
                    "description": f.get("description", ""),
                    "file_path": f.get("file_path"),
                    "severity": severity,
                    "estimated_minutes": estimated_minutes,
                    "impact": "medium",
                })

        # Sort by impact (high first) then estimated time (shortest first)
        impact_order = {"high": 0, "medium": 1, "low": 2}
        quick_wins.sort(key=lambda w: (impact_order.get(w["impact"], 2), w.get("estimated_minutes", 99)))

        return quick_wins[:10]  # Top 10

    def _generate_sprint_roadmap(self, findings: list[dict]) -> list[dict]:
        """Generate a sprint-based roadmap for addressing findings."""
        sprints = []

        # Sprint 1: Critical + High severity
        sprint1_items = [f for f in findings if f.get("severity") in ("critical", "high")]
        if sprint1_items:
            total_minutes = sum(f.get("estimated_fix_minutes", 30) for f in sprint1_items)
            sprints.append({
                "sprint": 1,
                "title": "Critical & High Priority Fixes",
                "items_count": len(sprint1_items),
                "estimated_hours": round(total_minutes / 60, 1),
                "focus_areas": list(set(f.get("category", "general") for f in sprint1_items)),
            })

        # Sprint 2: Medium severity
        sprint2_items = [f for f in findings if f.get("severity") == "medium"]
        if sprint2_items:
            total_minutes = sum(f.get("estimated_fix_minutes", 30) for f in sprint2_items)
            sprints.append({
                "sprint": 2,
                "title": "Medium Priority Improvements",
                "items_count": len(sprint2_items),
                "estimated_hours": round(total_minutes / 60, 1),
                "focus_areas": list(set(f.get("category", "general") for f in sprint2_items)),
            })

        # Sprint 3: Low severity + housekeeping
        sprint3_items = [f for f in findings if f.get("severity") in ("low", "info")]
        if sprint3_items:
            total_minutes = sum(f.get("estimated_fix_minutes", 15) for f in sprint3_items)
            sprints.append({
                "sprint": 3,
                "title": "Low Priority & Housekeeping",
                "items_count": len(sprint3_items),
                "estimated_hours": round(total_minutes / 60, 1),
                "focus_areas": list(set(f.get("category", "general") for f in sprint3_items)),
            })

        return sprints
