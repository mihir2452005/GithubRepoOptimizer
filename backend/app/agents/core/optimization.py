"""
RepositoryOptimizationAgent — Merges findings, computes optimization score,
generates Smart Quick Wins and category-aware Sprint Roadmap.
Includes effort estimates and breakdown by category.
"""

from collections import defaultdict

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class RepositoryOptimizationAgent(BaseAgent):
    name = "repository_optimization"
    version = "2.0.0"
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

        # Compute Optimization Score
        optimization_score = max(0, 100 - (critical_count * 5) - (high_count * 2))

        # Generate Smart Quick Wins
        quick_wins = self._generate_quick_wins(unique_findings)

        # Generate category-aware Sprint Roadmap
        sprint_roadmap = self._generate_sprint_roadmap(unique_findings)

        # Compute total estimated hours
        total_estimated_minutes = sum(
            f.get("estimated_fix_minutes", 30) for f in unique_findings
            if f.get("estimated_fix_minutes")
        )
        total_estimated_hours = round(total_estimated_minutes / 60, 1)

        # Effort breakdown by source agent category
        effort_breakdown = self._compute_effort_breakdown(unique_findings)

        # Priority-ordered findings for the report
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        unique_findings.sort(key=lambda f: priority_order.get(f.get("severity", "info"), 4))

        findings.append(AgentFinding(
            severity="info",
            description=f"Optimization Score: {optimization_score}/100",
            category="optimization_score",
            solution=f"Total estimated effort: {total_estimated_hours} hours across {len(unique_findings)} findings.",
            solution_code=f"# Effort breakdown:\n" + "\n".join(
                f"# {k}: {v}h" for k, v in effort_breakdown.items()
            ),
        ))

        summary = (
            f"Optimization Score: {optimization_score}/100. "
            f"Total unique findings: {len(unique_findings)} "
            f"(Critical: {critical_count}, High: {high_count}, "
            f"Medium: {medium_count}, Low: {low_count}). "
            f"Quick wins: {len(quick_wins)}. "
            f"Total estimated effort: {total_estimated_hours}h."
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
                "total_estimated_hours": total_estimated_hours,
                "effort_breakdown": effort_breakdown,
                "prioritized_findings": unique_findings[:20],
            },
            summary=summary,
        )

    def _generate_quick_wins(self, findings: list[dict]) -> list[dict]:
        """
        Quick Wins: ONLY include findings where estimated_fix_minutes <= 30
        AND fix_difficulty == "easy". If none meet criteria, fallback to top 5 by severity.
        """
        quick_wins = []

        for f in findings:
            fix_difficulty = f.get("fix_difficulty", "medium")
            estimated_minutes = f.get("estimated_fix_minutes", 30)

            if fix_difficulty == "easy" and estimated_minutes is not None and estimated_minutes <= 30:
                quick_wins.append({
                    "description": f.get("description", ""),
                    "file_path": f.get("file_path"),
                    "severity": f.get("severity", "low"),
                    "estimated_minutes": estimated_minutes,
                    "impact": "high" if f.get("severity") in ("critical", "high") else "medium",
                    "source_agent": f.get("source_agent", "unknown"),
                })

        # If no findings meet the criteria, fallback to top 5 by severity
        if not quick_wins:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            sorted_findings = sorted(findings, key=lambda x: severity_order.get(x.get("severity", "info"), 4))
            for f in sorted_findings[:5]:
                quick_wins.append({
                    "description": f.get("description", ""),
                    "file_path": f.get("file_path"),
                    "severity": f.get("severity", "low"),
                    "estimated_minutes": f.get("estimated_fix_minutes", 30),
                    "impact": "high" if f.get("severity") in ("critical", "high") else "medium",
                    "source_agent": f.get("source_agent", "unknown"),
                })
            return quick_wins

        # Sort by impact (high first) then estimated time (shortest first)
        impact_order = {"high": 0, "medium": 1, "low": 2}
        quick_wins.sort(key=lambda w: (impact_order.get(w["impact"], 2), w.get("estimated_minutes", 99)))

        return quick_wins[:10]

    def _generate_sprint_roadmap(self, findings: list[dict]) -> list[dict]:
        """
        Generate sprint roadmap based on actual finding distribution.
        The category with most findings gets Sprint 1.
        """
        sprints = []

        # Count findings per source agent
        category_counts: dict[str, list[dict]] = defaultdict(list)
        for f in findings:
            source = f.get("source_agent", "general")
            category_counts[source].append(f)

        # Sort categories by finding count (most findings first)
        sorted_categories = sorted(category_counts.items(), key=lambda x: -len(x[1]))

        for sprint_num, (category, cat_findings) in enumerate(sorted_categories[:4], 1):
            total_minutes = sum(f.get("estimated_fix_minutes", 30) for f in cat_findings)
            total_hours = round(total_minutes / 60, 1)

            severity_breakdown = {
                "critical": sum(1 for f in cat_findings if f.get("severity") == "critical"),
                "high": sum(1 for f in cat_findings if f.get("severity") == "high"),
                "medium": sum(1 for f in cat_findings if f.get("severity") == "medium"),
                "low": sum(1 for f in cat_findings if f.get("severity") == "low"),
            }

            category_display = category.replace("_", " ").title()
            sprints.append({
                "sprint": sprint_num,
                "title": f"{category_display} Improvements",
                "description": f"{len(cat_findings)} findings, estimated {total_hours} hours",
                "items_count": len(cat_findings),
                "estimated_hours": total_hours,
                "category": category,
                "severity_breakdown": severity_breakdown,
                "focus_areas": list(set(f.get("category", "general") for f in cat_findings)),
            })

        return sprints

    def _compute_effort_breakdown(self, findings: list[dict]) -> dict[str, float]:
        """Compute effort breakdown by source agent."""
        breakdown: dict[str, float] = defaultdict(float)

        for f in findings:
            source = f.get("source_agent", "general")
            minutes = f.get("estimated_fix_minutes", 30)
            # Map source agents to friendly category names
            category_map = {
                "security": "security",
                "code_quality": "code_quality",
                "architecture": "architecture",
                "technical_debt": "debt",
            }
            category = category_map.get(source, source)
            breakdown[category] += minutes / 60

        return {k: round(v, 1) for k, v in breakdown.items()}
