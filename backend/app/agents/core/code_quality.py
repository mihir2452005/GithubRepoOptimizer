"""
CodeQualityAgent — Analyzes code quality metrics.
Identifies very long files, long functions, and basic complexity indicators.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


# Extensions to analyze for code quality
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go",
    ".rb", ".php", ".c", ".cpp", ".cs", ".rs", ".kt", ".scala",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next", "target",
}

# Thresholds
MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50


class CodeQualityAgent(BaseAgent):
    name = "code_quality"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        total_lines = 0
        files_analyzed = 0
        long_files = 0
        long_functions = 0

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext.lower() not in CODE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)
                files_analyzed += 1

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except (OSError, UnicodeDecodeError):
                    continue

                line_count = len(lines)
                total_lines += line_count

                # Check for very long files
                if line_count > MAX_FILE_LINES:
                    long_files += 1
                    findings.append(AgentFinding(
                        severity="medium",
                        description=f"File has {line_count} lines (threshold: {MAX_FILE_LINES}). Consider splitting.",
                        file_path=rel_path,
                        category="file_length",
                        solution=f"Split this {line_count}-line file into smaller, focused modules. Extract related functions/classes into separate files grouped by responsibility. Aim for <300 lines per file.",
                        solution_code=f"# Split {rel_path} into smaller modules:\n# {rel_path.replace('.py', '')}/\n#   ├── models.py      (data classes/models)\n#   ├── services.py    (business logic)\n#   ├── utils.py       (helper functions)\n#   └── __init__.py    (re-exports)",
                        solution_reference="https://refactoring.guru/smells/large-class",
                        fix_difficulty="medium",
                        estimated_fix_minutes=30,
                    ))

                # Detect long functions (simple heuristic)
                func_findings = self._detect_long_functions(lines, rel_path, ext.lower())
                long_functions += len(func_findings)
                findings.extend(func_findings)

        avg_file_length = total_lines / max(files_analyzed, 1)

        summary = (
            f"Analyzed {files_analyzed} code files ({total_lines} total lines). "
            f"Found {long_files} oversized files and {long_functions} long functions."
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "files_analyzed": files_analyzed,
                "total_lines": total_lines,
                "average_file_length": round(avg_file_length, 1),
                "long_files_count": long_files,
                "long_functions_count": long_functions,
            },
            summary=summary,
        )

    def _detect_long_functions(
        self, lines: list[str], rel_path: str, ext: str
    ) -> list[AgentFinding]:
        """Detect functions that exceed the line threshold."""
        findings: list[AgentFinding] = []

        # Simple function detection patterns
        if ext == ".py":
            pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)")
        elif ext in {".js", ".ts", ".tsx", ".jsx"}:
            pattern = re.compile(r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)")
        elif ext in {".java", ".go", ".cs", ".kt"}:
            pattern = re.compile(r"(?:public|private|protected|func|fun)\s+\w*\s*(\w+)\s*\(")
        else:
            return findings

        func_start: int | None = None
        func_name: str = ""
        indent_level: int = 0

        for i, line in enumerate(lines):
            match = pattern.match(line) if ext == ".py" else pattern.search(line)
            if match:
                # Check if previous function was too long
                if func_start is not None:
                    func_length = i - func_start
                    if func_length > MAX_FUNCTION_LINES:
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"Function '{func_name}' is {func_length} lines (threshold: {MAX_FUNCTION_LINES})",
                            file_path=rel_path,
                            line_number=func_start + 1,
                            category="function_length",
                            solution=f"Break '{func_name}' into smaller functions. Extract logical steps into helper methods with descriptive names. Each function should do one thing.",
                            solution_code=f"# Before: one large function\n# def {func_name}(...):\n#     ... {func_length} lines ...\n\n# After: extract helpers\ndef {func_name}(...):\n    data = _validate_input(...)\n    result = _process_data(data)\n    return _format_output(result)\n\ndef _validate_input(...):\n    ...\n\ndef _process_data(data):\n    ...",
                            solution_reference="https://refactoring.guru/smells/long-method",
                            fix_difficulty="medium",
                            estimated_fix_minutes=20,
                        ))

                # Track new function
                func_start = i
                groups = match.groups()
                func_name = next((g for g in groups if g), "anonymous")
                indent_level = len(line) - len(line.lstrip())

        # Check last function
        if func_start is not None:
            func_length = len(lines) - func_start
            if func_length > MAX_FUNCTION_LINES:
                findings.append(AgentFinding(
                    severity="low",
                    description=f"Function '{func_name}' is {func_length} lines (threshold: {MAX_FUNCTION_LINES})",
                    file_path=rel_path,
                    line_number=func_start + 1,
                    category="function_length",
                    solution=f"Break '{func_name}' into smaller functions. Extract logical steps into helper methods with descriptive names.",
                    solution_code=f"# Refactor: split '{func_name}' into focused helper functions\n# Each function should be <50 lines and do one thing well.",
                    solution_reference="https://refactoring.guru/smells/long-method",
                    fix_difficulty="medium",
                    estimated_fix_minutes=20,
                ))

        return findings
