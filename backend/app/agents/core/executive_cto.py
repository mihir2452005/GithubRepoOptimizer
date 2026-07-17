"""
ExecutiveCTOAgent — Strategic executive overview of repository health.
PURPOSE: Provides CTO-level decision support — health grade, risk assessment,
top 3 strategic recommendations, and production readiness verdict.
This is DIFFERENT from the Optimization Agent which provides tactical sprint planning.

Executive Summary = "What's the overall status and what should leadership know?"
Optimization Agent = "What specific things should developers fix, in what order?"
"""

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class ExecutiveCTOAgent(BaseAgent):
    name = "executive_cto"
    version = "1.1.0"
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

        # Health grade
        health_grade = self._compute_health_grade(total_critical, total_high, total_medium, total_low)

        # Production readiness
        production_ready = total_critical == 0 and total_high <= 2
        production_status = "Ready for production" if production_ready else (
            "NOT ready — critical issues must be resolved" if total_critical > 0
            else "Almost ready — address high-severity issues first"
        )

        # Strategic recommendations (leadership-level)
        recommendations = self._generate_recommendations(
            total_critical, total_high, total_medium, prior_results
        )

        # Risk assessment
        risk_level = "Critical" if total_critical > 3 else (
            "High" if total_critical > 0 or total_high > 5 else (
                "Medium" if total_high > 0 or total_medium > 10 else "Low"
            )
        )

        # Executive findings — high-level strategic observations
        findings.append(AgentFinding(
            severity="info" if production_ready else "high",
            description=f"Production Readiness: {production_status}",
            category="executive_assessment",
            solution=f"Overall risk level: {risk_level}. {recommendations[0] if recommendations else ''}",
        ))

        if total_critical > 0:
            findings.append(AgentFinding(
                severity="critical",
                description=f"⚠️ {total_critical} CRITICAL issues found — these pose immediate security or stability risks and must be resolved before any production deployment.",
                category="executive_assessment",
                solution="Block deployments until critical issues are resolved. Assign senior engineers to each critical finding. Schedule emergency review within 48 hours.",
            ))

        summary = (
            f"📊 EXECUTIVE SUMMARY\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Health Grade: {health_grade} | Risk Level: {risk_level}\n"
            f"Production Status: {production_status}\n"
            f"Total Findings: {total_findings} (🔴 {total_critical} Critical, 🟠 {total_high} High, 🟡 {total_medium} Medium, 🔵 {total_low} Low)\n\n"
            f"TOP STRATEGIC RECOMMENDATIONS:\n"
            + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(recommendations[:3]))
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "health_grade": health_grade,
                "risk_level": risk_level,
                "production_ready": production_ready,
                "production_status": production_status,
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
