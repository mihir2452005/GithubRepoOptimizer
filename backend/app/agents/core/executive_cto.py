"""
ExecutiveCTOAgent — Synthesizes findings from all other agents into an executive summary.
Provides high-level strategic recommendations for the repository.
"""

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class ExecutiveCTOAgent(BaseAgent):
    name = "executive_cto"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        findings: list[AgentFinding] = []
        prior_results: dict = payload.metadata.get("prior_results", {})

        # Aggregate findings from prior results
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0
        total_findings = 0
        agent_summaries: list[str] = []

        for agent_name, result in prior_results.items():
            if isinstance(result, dict):
                agent_findings = result.get("findings", [])
                total_findings += len(agent_findings)
                for f in agent_findings:
                    sev = f.get("severity", "info") if isinstance(f, dict) else "info"
                    if sev == "critical":
                        total_critical += 1
                    elif sev == "high":
                        total_high += 1
                    elif sev == "medium":
                        total_medium += 1
                    elif sev == "low":
                        total_low += 1

                summary = result.get("summary", "")
                if summary:
                    agent_summaries.append(f"[{agent_name}] {summary}")

        # Generate executive findings
        if total_critical > 0:
            findings.append(AgentFinding(
                severity="critical",
                description=f"Repository has {total_critical} critical issues requiring immediate attention",
                category="executive_summary",
                fix_difficulty="hard",
                estimated_fix_minutes=total_critical * 30,
            ))

        if total_high > 5:
            findings.append(AgentFinding(
                severity="high",
                description=f"High issue density detected ({total_high} high-severity findings). Recommend dedicated sprint.",
                category="executive_summary",
                fix_difficulty="hard",
                estimated_fix_minutes=total_high * 20,
            ))

        # Health grade
        health_grade = self._compute_health_grade(total_critical, total_high, total_medium, total_low)

        # Strategic recommendations
        recommendations = self._generate_recommendations(
            total_critical, total_high, total_medium, prior_results
        )

        summary = (
            f"Executive Summary — Health Grade: {health_grade}\n"
            f"Total findings: {total_findings} "
            f"(Critical: {total_critical}, High: {total_high}, "
            f"Medium: {total_medium}, Low: {total_low})\n"
            f"Recommendations: {'; '.join(recommendations[:3])}"
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "health_grade": health_grade,
                "total_findings": total_findings,
                "severity_breakdown": {
                    "critical": total_critical,
                    "high": total_high,
                    "medium": total_medium,
                    "low": total_low,
                },
                "recommendations": recommendations,
                "agent_summaries": agent_summaries,
            },
            summary=summary,
        )

    def _compute_health_grade(
        self, critical: int, high: int, medium: int, low: int
    ) -> str:
        """Compute a letter grade for repository health."""
        score = 100 - (critical * 15) - (high * 5) - (medium * 2) - (low * 0.5)
        score = max(0, min(100, score))

        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _generate_recommendations(
        self, critical: int, high: int, medium: int, prior_results: dict
    ) -> list[str]:
        """Generate strategic recommendations based on findings."""
        recommendations = []

        if critical > 0:
            recommendations.append(
                "URGENT: Address all critical security vulnerabilities before next deployment"
            )

        if high > 3:
            recommendations.append(
                "Schedule a focused code health sprint to address high-severity issues"
            )

        # Check for specific agent results
        if "technical_debt" in prior_results:
            debt_metrics = prior_results["technical_debt"].get("metrics", {})
            if debt_metrics.get("debt_score", 0) > 50:
                recommendations.append(
                    "Technical debt is significant. Allocate 20% of sprint capacity for debt reduction"
                )

        if "dependency" in prior_results:
            dep_metrics = prior_results["dependency"].get("metrics", {})
            if dep_metrics.get("total_dependencies", 0) > 50:
                recommendations.append(
                    "Dependency count is high. Audit and prune unused dependencies"
                )

        if "architecture" in prior_results:
            arch_metrics = prior_results["architecture"].get("metrics", {})
            if arch_metrics.get("circular_dependencies", 0) > 0:
                recommendations.append(
                    "Resolve circular dependencies to improve modularity and testability"
                )

        if not recommendations:
            recommendations.append("Repository is in good health. Maintain current practices.")

        return recommendations
