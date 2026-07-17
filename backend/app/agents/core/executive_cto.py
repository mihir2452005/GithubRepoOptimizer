"""
ExecutiveCTOAgent — Strategic executive overview of repository health.
PURPOSE: Provides CTO-level decision support — health grade, risk assessment,
top 3 strategic recommendations, production readiness checklist, and
engineering maturity level.

Executive Summary = "What's the overall status and what should leadership know?"
Optimization Agent = "What specific things should developers fix, in what order?"
"""

import os

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class ExecutiveCTOAgent(BaseAgent):
    name = "executive_cto"
    version = "2.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        findings: list[AgentFinding] = []
        prior_results: dict = payload.metadata.get("prior_results", {})
        repo_path = payload.repo_path

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

        # Production readiness checklist
        production_readiness_checklist = self._compute_production_checklist(
            repo_path, total_critical, prior_results
        )
        passed_checks = sum(1 for v in production_readiness_checklist.values() if v)
        total_checks = len(production_readiness_checklist)
        production_readiness_score = round((passed_checks / max(total_checks, 1)) * 100)

        # Engineering maturity level
        engineering_maturity_level = self._compute_maturity_level(production_readiness_score)

        # Production readiness verdict
        production_ready = total_critical == 0 and total_high <= 2
        production_status = "Ready for production" if production_ready else (
            "NOT ready — critical issues must be resolved" if total_critical > 0
            else "Almost ready — address high-severity issues first"
        )

        # Strategic recommendations (leadership-level)
        recommendations = self._generate_recommendations(
            total_critical, total_high, total_medium, prior_results, production_readiness_checklist
        )

        # Risk assessment
        risk_level = "Critical" if total_critical > 3 else (
            "High" if total_critical > 0 or total_high > 5 else (
                "Medium" if total_high > 0 or total_medium > 10 else "Low"
            )
        )

        # Executive findings
        findings.append(AgentFinding(
            severity="info" if production_ready else "high",
            description=f"Production Readiness: {production_status}",
            category="executive_assessment",
            solution=f"Overall risk level: {risk_level}. {recommendations[0] if recommendations else ''}",
            solution_code=f"# Production Readiness Score: {production_readiness_score}%\n# Engineering Maturity: {engineering_maturity_level}\n# Checklist:\n" + "\n".join(
                f"# {'✅' if v else '❌'} {k}" for k, v in production_readiness_checklist.items()
            ),
        ))

        if total_critical > 0:
            findings.append(AgentFinding(
                severity="critical",
                description=f"⚠️ {total_critical} CRITICAL issues found — immediate security or stability risks",
                category="executive_assessment",
                solution="Block deployments until critical issues are resolved. Assign senior engineers to each critical finding. Schedule emergency review within 48 hours.",
                solution_code="# Priority action plan:\n# 1. Review all critical findings immediately\n# 2. Create hotfix branch for each critical issue\n# 3. Implement fixes with corresponding tests\n# 4. Conduct security review before merge\n# 5. Deploy with monitoring enabled",
            ))

        # Checklist findings for missing items
        missing_items = [k for k, v in production_readiness_checklist.items() if not v]
        if missing_items:
            findings.append(AgentFinding(
                severity="medium",
                description=f"Production readiness: {len(missing_items)} checklist items failing: {', '.join(missing_items)}",
                category="production_readiness",
                solution=f"Address the failing checklist items to improve production readiness. Current score: {production_readiness_score}%. Target: 90%+.",
                solution_code="# Production checklist actions:\n" + "\n".join(
                    f"# - {item}: {self._get_checklist_fix(item)}" for item in missing_items
                ),
                fix_difficulty="medium",
                estimated_fix_minutes=60,
            ))

        summary = (
            f"📊 EXECUTIVE SUMMARY\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Health Grade: {health_grade} | Risk Level: {risk_level}\n"
            f"Production Status: {production_status}\n"
            f"Production Readiness: {production_readiness_score}% | Maturity: {engineering_maturity_level}\n"
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
                "production_readiness_checklist": production_readiness_checklist,
                "production_readiness_score": production_readiness_score,
                "engineering_maturity_level": engineering_maturity_level,
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

    def _compute_production_checklist(
        self, repo_path: str, total_critical: int, prior_results: dict
    ) -> dict[str, bool]:
        """Compute production readiness checklist by checking file existence."""
        checklist: dict[str, bool] = {}

        # has_ci_cd: .github/workflows/ exists
        ci_path = os.path.join(repo_path, ".github", "workflows")
        gitlab_ci = os.path.join(repo_path, ".gitlab-ci.yml")
        checklist["has_ci_cd"] = os.path.isdir(ci_path) or os.path.isfile(gitlab_ci)

        # has_tests: test files detected
        has_tests = False
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv"}]
            for f in files:
                if f.startswith("test_") or f.endswith("_test.py") or f.endswith(".test.ts") or f.endswith(".test.js") or f.endswith(".spec.ts") or f.endswith(".spec.js"):
                    has_tests = True
                    break
            if has_tests:
                break
        checklist["has_tests"] = has_tests

        # has_readme: README.md exists and > 100 chars
        readme_path = os.path.join(repo_path, "README.md")
        readme_exists = os.path.isfile(readme_path)
        if readme_exists:
            try:
                readme_size = os.path.getsize(readme_path)
                checklist["has_readme"] = readme_size > 100
            except OSError:
                checklist["has_readme"] = False
        else:
            checklist["has_readme"] = False

        # has_license: LICENSE file exists
        license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]
        checklist["has_license"] = any(
            os.path.isfile(os.path.join(repo_path, f)) for f in license_files
        )

        # no_critical_vulns: 0 critical findings
        checklist["no_critical_vulns"] = total_critical == 0

        # has_error_handling: try/except or try/catch detected
        has_error_handling = False
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}]
            for f in files:
                if f.endswith((".py", ".js", ".ts")):
                    try:
                        filepath = os.path.join(root, f)
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read(5000)  # Check first 5KB
                            if "try:" in content or "try {" in content or "try{" in content:
                                has_error_handling = True
                                break
                    except OSError:
                        continue
            if has_error_handling:
                break
        checklist["has_error_handling"] = has_error_handling

        # has_env_config: .env.example or config file exists
        env_files = [".env.example", ".env.sample", "config.yaml", "config.yml", "config.json", "settings.py"]
        checklist["has_env_config"] = any(
            os.path.isfile(os.path.join(repo_path, f)) for f in env_files
        )

        # has_docker: Dockerfile exists
        checklist["has_docker"] = os.path.isfile(os.path.join(repo_path, "Dockerfile")) or os.path.isfile(os.path.join(repo_path, "docker-compose.yml"))

        return checklist

    def _compute_maturity_level(self, readiness_score: int) -> str:
        """Compute engineering maturity level based on readiness score."""
        if readiness_score >= 90:
            return "Enterprise"
        elif readiness_score >= 70:
            return "Advanced"
        elif readiness_score >= 40:
            return "Intermediate"
        else:
            return "Beginner"

    def _get_checklist_fix(self, item: str) -> str:
        """Get fix instructions for a checklist item."""
        fixes = {
            "has_ci_cd": "Add .github/workflows/ci.yml with build+test steps",
            "has_tests": "Create test files using pytest (Python) or jest (JS/TS)",
            "has_readme": "Write a README.md with setup instructions and usage examples",
            "has_license": "Add a LICENSE file (MIT, Apache 2.0, etc.)",
            "no_critical_vulns": "Fix all critical security vulnerabilities",
            "has_error_handling": "Add try/except blocks around I/O and external calls",
            "has_env_config": "Create .env.example documenting required env variables",
            "has_docker": "Add a Dockerfile for consistent deployment",
        }
        return fixes.get(item, "Address this item")

    def _generate_recommendations(
        self, critical: int, high: int, medium: int, prior_results: dict,
        checklist: dict[str, bool]
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

        # Checklist-driven recommendations
        if not checklist.get("has_ci_cd"):
            recommendations.append(
                "Set up CI/CD pipeline — automated testing prevents regressions"
            )
        if not checklist.get("has_tests"):
            recommendations.append(
                "Add automated tests — untested code is the highest-risk debt"
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
