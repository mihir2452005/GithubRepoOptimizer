"""
TechnicalDebtAgent — Comprehensive technical debt analysis.
Detects TODO/FIXME/HACK markers, missing docstrings, functions without
error handling that do I/O, and files without corresponding tests.
Calculates estimated hours and debt category breakdown.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


# Patterns that indicate technical debt
DEBT_PATTERNS: list[tuple[str, str, str]] = [
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

PYTHON_EXTENSIONS = {".py"}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next", "target",
}

# I/O function patterns that indicate risky code without error handling
IO_PATTERNS = re.compile(
    r"\b(open|requests\.(get|post|put|delete|patch)|fetch|urllib|urlopen|"
    r"subprocess\.(run|call|Popen)|shutil\.(copy|move|rmtree)|"
    r"os\.(remove|rename|makedirs|listdir)|json\.(load|dump))\s*\("
)


class TechnicalDebtAgent(BaseAgent):
    name = "technical_debt"
    version = "2.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        files_scanned = 0
        debt_by_type: dict[str, int] = {}

        # Debt category counters
        todo_count = 0
        missing_docstrings = 0
        missing_error_handling = 0
        missing_tests = 0

        # Build regex for all debt markers
        markers = "|".join(p[0] for p in DEBT_PATTERNS)
        debt_regex = re.compile(rf"\b({markers})\b", re.IGNORECASE)

        # Collect all Python files for test coverage check
        python_files: list[str] = []
        test_files: set[str] = set()

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext.lower() not in CODE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)
                files_scanned += 1

                # Track Python files and test files
                if ext.lower() == ".py":
                    if filename.startswith("test_") or filename.endswith("_test.py") or "/test" in rel_path.replace(os.sep, "/"):
                        test_files.add(filename)
                    else:
                        python_files.append(rel_path)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        lines = content.splitlines()
                except (OSError, UnicodeDecodeError):
                    continue

                # === TODO/FIXME/HACK detection ===
                for line_num, line in enumerate(lines, 1):
                    match = debt_regex.search(line)
                    if match:
                        marker = match.group(1).upper()
                        debt_by_type[marker] = debt_by_type.get(marker, 0) + 1
                        todo_count += 1
                        context = line.strip()[:120]

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
                                    fix_difficulty="easy",
                                    estimated_fix_minutes=15,
                                ))
                                break

                # === Python-specific debt checks ===
                if ext.lower() == ".py":
                    # Missing docstrings
                    docstring_findings = self._check_missing_docstrings(lines, rel_path)
                    missing_docstrings += len(docstring_findings)
                    findings.extend(docstring_findings)

                    # Missing error handling for I/O operations
                    io_findings = self._check_missing_error_handling(lines, rel_path)
                    missing_error_handling += len(io_findings)
                    findings.extend(io_findings)

        # === Missing test files ===
        test_findings = self._check_missing_tests(python_files, test_files, repo_path)
        missing_tests = len(test_findings)
        findings.extend(test_findings)

        # === Calculate estimated hours ===
        total_estimated_hours = round(
            todo_count * 0.5 +
            missing_docstrings * 1.0 +
            missing_tests * 2.0 +
            missing_error_handling * 1.0,
            1
        )

        # Debt categories breakdown
        code_debt = todo_count
        test_debt = missing_tests
        doc_debt = missing_docstrings
        robustness_debt = missing_error_handling

        # Calculate debt score
        total_markers = sum(debt_by_type.values())
        debt_score = self._calculate_debt_score(total_markers, files_scanned)

        summary = (
            f"Scanned {files_scanned} files. "
            f"Found {total_markers} TODO/FIXME markers, {missing_docstrings} missing docstrings, "
            f"{missing_tests} untested files, {missing_error_handling} unguarded I/O operations. "
            f"Estimated effort: {total_estimated_hours} hours. "
            f"Debt score: {debt_score}/100 (lower is better)."
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
                "missing_docstrings": missing_docstrings,
                "missing_tests": missing_tests,
                "missing_error_handling": missing_error_handling,
                "total_estimated_hours": total_estimated_hours,
                "debt_categories": {
                    "code_debt": code_debt,
                    "test_debt": test_debt,
                    "doc_debt": doc_debt,
                    "robustness_debt": robustness_debt,
                },
            },
            summary=summary,
        )

    def _check_missing_docstrings(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Detect Python functions without docstrings."""
        findings: list[AgentFinding] = []
        func_re = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(")

        for i, line in enumerate(lines):
            match = func_re.match(line)
            if match:
                func_name = match.group(2)
                # Skip private/dunder methods
                if func_name.startswith("_"):
                    continue

                # Check if next non-empty line is a docstring
                has_docstring = False
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if next_line.startswith(('"""', "'''", '"', "'")):
                        has_docstring = True
                    break

                if not has_docstring:
                    if len(findings) < 15:  # Limit to avoid noise
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"Function '{func_name}' has no docstring",
                            file_path=rel_path,
                            line_number=i + 1,
                            category="missing_docstring",
                            solution=f"Add a docstring to '{func_name}' explaining what it does, its parameters, and return value. This helps maintainability and auto-documentation tools.",
                            solution_code=f'def {func_name}(...):\n    """Brief description of what {func_name} does.\n\n    Args:\n        param1: Description of param1.\n\n    Returns:\n        Description of return value.\n\n    Raises:\n        ValueError: When input is invalid.\n    """\n    ...',
                            fix_difficulty="easy",
                            estimated_fix_minutes=5,
                        ))

        return findings

    def _check_missing_error_handling(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Detect I/O operations without try/except wrapping."""
        findings: list[AgentFinding] = []
        # Track indentation of try blocks
        try_indent_stack: list[int] = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track try blocks
            if stripped.startswith("try:"):
                indent = len(line) - len(line.lstrip())
                try_indent_stack.append(indent)
            elif stripped.startswith(("except", "finally:")):
                # Pop try blocks at this level
                indent = len(line) - len(line.lstrip())
                try_indent_stack = [t for t in try_indent_stack if t < indent]

            # Check for I/O operations
            if IO_PATTERNS.search(line):
                current_indent = len(line) - len(line.lstrip())
                # Check if we're inside a try block
                in_try = any(t < current_indent for t in try_indent_stack)
                if not in_try:
                    if len(findings) < 10:
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"I/O operation without error handling",
                            file_path=rel_path,
                            line_number=i + 1,
                            category="missing_error_handling",
                            solution="Wrap I/O operations in try/except to handle failures gracefully. Network calls, file operations, and subprocess calls can all fail unexpectedly.",
                            solution_code="# Wrap I/O in try/except:\ntry:\n    result = risky_io_operation()\nexcept (OSError, IOError) as e:\n    logger.error(f'I/O operation failed: {e}')\n    # handle gracefully: retry, fallback, or re-raise\n    raise\nexcept requests.RequestException as e:\n    logger.error(f'Network request failed: {e}')\n    # implement retry logic or return cached data",
                            fix_difficulty="easy",
                            estimated_fix_minutes=10,
                        ))

        return findings

    def _check_missing_tests(self, python_files: list[str], test_files: set[str], repo_path: str) -> list[AgentFinding]:
        """Check for Python files that don't have corresponding test files."""
        findings: list[AgentFinding] = []

        for rel_path in python_files:
            filename = os.path.basename(rel_path)
            # Skip __init__, config, etc.
            if filename in ("__init__.py", "conftest.py", "setup.py", "manage.py"):
                continue
            if "migration" in rel_path.lower() or "config" in filename.lower():
                continue

            # Check if a test file exists for this module
            base_name = filename.removesuffix(".py")
            expected_test_names = {
                f"test_{filename}",
                f"{base_name}_test.py",
                f"test_{base_name}.py",
            }

            has_test = bool(expected_test_names & test_files)
            if not has_test:
                if len(findings) < 15:
                    findings.append(AgentFinding(
                        severity="low",
                        description=f"No test file found for '{rel_path}'",
                        file_path=rel_path,
                        category="missing_test",
                        solution=f"Create a test file for '{filename}'. Untested code is a liability — it can break without anyone noticing. Add unit tests covering the main logic paths.",
                        solution_code=f"# Create: tests/test_{base_name}.py\nimport pytest\nfrom {base_name} import *  # adjust import path\n\n\nclass Test{base_name.title().replace('_', '')}:\n    def test_basic_functionality(self):\n        # Arrange\n        ...\n        # Act\n        result = function_under_test(...)\n        # Assert\n        assert result == expected\n\n    def test_error_case(self):\n        with pytest.raises(ValueError):\n            function_under_test(invalid_input)",
                        fix_difficulty="medium",
                        estimated_fix_minutes=30,
                    ))

        return findings

    def _calculate_debt_score(self, total_markers: int, files_scanned: int) -> int:
        """Calculate a technical debt score (0-100, lower is better)."""
        if files_scanned == 0:
            return 0

        density = total_markers / files_scanned

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
            "FIXME": "This indicates a known bug. Fix the underlying issue — don't leave broken code in production. Create a high-priority bug ticket if you can't fix it now.",
            "HACK": "Replace this workaround with a proper solution. Hacks accumulate and make the codebase fragile. Refactor to use the correct approach.",
            "XXX": "This marks dangerous or problematic code. Review carefully, understand the risk, and implement a proper fix.",
            "TEMP": "Remove this temporary code. If it's still needed, make it permanent with proper implementation and tests.",
            "DEPRECATED": "Remove or replace this deprecated code. Check the library/framework docs for the modern replacement API.",
            "WORKAROUND": "Replace this workaround with the proper fix now that the underlying issue may be resolved. Check if upstream fixes are available.",
        }
        return solutions.get(marker, f"Address the '{marker}' concern described in the comment, then remove the marker.")
