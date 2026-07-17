"""
TechnicalDebtAgent — Identifies technical debt markers in code.
Scans for TODO, FIXME, HACK, XXX comments and estimates debt load.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


# Patterns that indicate technical debt
DEBT_PATTERNS: list[tuple[str, str, str]] = [
    # (marker, severity, description_prefix)
    ("TODO", "low", "TODO comment"),
    ("FIXME", "medium", "FIXME — known bug or issue"),
    ("HACK", "medium", "HACK — workaround in place"),
    ("XXX", "medium", "XXX — requires attention"),
    ("TEMP", "low", "Temporary code that should be removed"),
    ("DEPRECATED", "low", "Deprecated code still in use"),
    ("WORKAROUND", "medium", "Workaround for an underlying issue"),
]

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go",
    ".rb", ".php", ".c", ".cpp", ".cs", ".rs", ".kt", ".scala",
    ".sh", ".bash",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next", "target",
}


class TechnicalDebtAgent(BaseAgent):
    name = "technical_debt"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        files_scanned = 0
        debt_by_type: dict[str, int] = {}

        # Build regex for all debt markers
        markers = "|".join(p[0] for p in DEBT_PATTERNS)
        debt_regex = re.compile(rf"\b({markers})\b", re.IGNORECASE)

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext.lower() not in CODE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)
                files_scanned += 1

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            match = debt_regex.search(line)
                            if match:
                                marker = match.group(1).upper()
                                debt_by_type[marker] = debt_by_type.get(marker, 0) + 1

                                # Get context from the comment
                                context = line.strip()[:120]

                                # Find matching pattern info
                                for pattern_marker, severity, desc_prefix in DEBT_PATTERNS:
                                    if marker == pattern_marker:
                                        solution = self._get_debt_solution(marker, context)
                                        findings.append(AgentFinding(
                                            severity=severity,
                                            description=f"{desc_prefix}: {context}",
                                            file_path=rel_path,
                                            line_number=line_num,
                                            category="technical_debt",
                                            solution=solution,
                                            solution_code=f"# Remove this {marker} by implementing the fix:\n# Original: {context}\n# Action: Address the concern, then remove the {marker} comment",
                                            solution_reference="https://refactoring.guru/refactoring/techniques",
                                            fix_difficulty="easy",
                                            estimated_fix_minutes=15,
                                        ))
                                        break
                except (OSError, UnicodeDecodeError):
                    continue

        # Calculate debt score
        total_markers = sum(debt_by_type.values())
        debt_score = self._calculate_debt_score(total_markers, files_scanned)

        summary = (
            f"Scanned {files_scanned} files. Found {total_markers} technical debt markers. "
            f"Debt score: {debt_score}/100 (lower is better). "
            f"Breakdown: {', '.join(f'{k}: {v}' for k, v in sorted(debt_by_type.items(), key=lambda x: -x[1]))}"
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "files_scanned": files_scanned,
                "total_debt_markers": total_markers,
                "debt_by_type": debt_by_type,
                "debt_score": debt_score,
                "debt_density": round(total_markers / max(files_scanned, 1), 2),
            },
            summary=summary,
        )

    def _calculate_debt_score(self, total_markers: int, files_scanned: int) -> int:
        """
        Calculate a technical debt score (0-100, lower is better).
        Based on density of debt markers relative to codebase size.
        """
        if files_scanned == 0:
            return 0

        density = total_markers / files_scanned

        # Score mapping: density -> score
        if density < 0.1:
            return int(density * 100)
        elif density < 0.5:
            return int(10 + (density - 0.1) * 50)
        elif density < 1.0:
            return int(30 + (density - 0.5) * 60)
        elif density < 2.0:
            return int(60 + (density - 1.0) * 30)
        else:
            return min(100, int(90 + (density - 2.0) * 5))

    def _get_debt_solution(self, marker: str, context: str) -> str:
        """Generate solution text based on debt marker type."""
        solutions = {
            "TODO": "Implement the TODO item now or create a tracked issue/ticket for it. If it's been there for >30 days, either do it or delete it.",
            "FIXME": "This indicates a known bug. Fix the underlying issue — don't leave broken code in production. If you can't fix it now, create a high-priority bug ticket.",
            "HACK": "Replace this workaround with a proper solution. Hacks accumulate and make the codebase fragile. Refactor to use the correct approach.",
            "XXX": "This marks dangerous or problematic code. Review carefully, understand the risk, and implement a proper fix. Document why it exists if it must stay temporarily.",
            "DEPRECATED": "Remove or replace this deprecated code. Check the library/framework docs for the modern replacement API.",
            "REFACTOR": "Schedule time to refactor this section. Apply SOLID principles, extract methods, and improve naming.",
            "OPTIMIZE": "Profile this code to confirm it's actually slow before optimizing. If confirmed, apply algorithmic improvements or caching.",
            "REVIEW": "Get a code review on this section. If the review concern has been addressed, remove the marker.",
        }
        return solutions.get(marker, f"Address the '{marker}' concern described in the comment, then remove the marker to reduce debt.")
