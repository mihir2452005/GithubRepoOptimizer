"""
CodeQualityAgent — Production-grade code quality analysis.
Detects cyclomatic complexity, unused imports, magic numbers,
empty exception handlers, and naming convention violations.
"""

import os
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


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
COMPLEXITY_THRESHOLD = 10

# Complexity keywords
COMPLEXITY_KEYWORDS = re.compile(
    r"\b(if|elif|else\s+if|for|while|except|catch|case)\b|(\band\b|\bor\b|\b\?\s*:)"
)


class CodeQualityAgent(BaseAgent):
    name = "code_quality"
    version = "2.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        total_lines = 0
        files_analyzed = 0
        long_files = 0
        long_functions = 0
        complexity_issues = 0
        unused_import_count = 0
        magic_number_count = 0
        empty_except_count = 0
        naming_issues = 0

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
                        content = f.read()
                        lines = content.splitlines()
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
                        solution=f"Split this {line_count}-line file into smaller, focused modules. Extract related functions/classes into separate files grouped by responsibility.",
                        solution_code=f"# Split {rel_path} into smaller modules:\n# {os.path.splitext(rel_path)[0]}/\n#   ├── models.py      (data classes/models)\n#   ├── services.py    (business logic)\n#   ├── utils.py       (helper functions)\n#   └── __init__.py    (re-exports)",
                        fix_difficulty="medium",
                        estimated_fix_minutes=30,
                    ))

                # Python-specific checks
                if ext.lower() == ".py":
                    # Cyclomatic complexity
                    complexity_findings = self._check_complexity(lines, rel_path)
                    complexity_issues += len(complexity_findings)
                    findings.extend(complexity_findings)

                    # Unused imports
                    import_findings = self._check_unused_imports(content, lines, rel_path)
                    unused_import_count += len(import_findings)
                    findings.extend(import_findings)

                    # Empty except blocks
                    except_findings = self._check_empty_except(lines, rel_path)
                    empty_except_count += len(except_findings)
                    findings.extend(except_findings)

                    # Naming conventions (Python: snake_case functions, PascalCase classes)
                    naming_findings = self._check_python_naming(lines, rel_path)
                    naming_issues += len(naming_findings)
                    findings.extend(naming_findings)

                # JS/TS-specific checks
                elif ext.lower() in {".js", ".ts", ".tsx", ".jsx"}:
                    # Naming conventions (JS: camelCase functions, PascalCase classes/components)
                    naming_findings = self._check_js_naming(lines, rel_path)
                    naming_issues += len(naming_findings)
                    findings.extend(naming_findings)

                # Magic number detection (all languages)
                magic_findings = self._check_magic_numbers(lines, rel_path, ext.lower())
                magic_number_count += len(magic_findings)
                findings.extend(magic_findings)

                # Long function detection
                func_findings = self._detect_long_functions(lines, rel_path, ext.lower())
                long_functions += len(func_findings)
                findings.extend(func_findings)

        avg_file_length = total_lines / max(files_analyzed, 1)

        summary = (
            f"Analyzed {files_analyzed} code files ({total_lines} total lines). "
            f"Found {long_files} oversized files, {long_functions} long functions, "
            f"{complexity_issues} high-complexity functions, {unused_import_count} unused imports, "
            f"{magic_number_count} magic numbers, {empty_except_count} empty excepts, "
            f"{naming_issues} naming issues."
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
                "complexity_issues": complexity_issues,
                "unused_imports": unused_import_count,
                "magic_numbers": magic_number_count,
                "empty_excepts": empty_except_count,
                "naming_issues": naming_issues,
            },
            summary=summary,
        )

    def _check_complexity(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Check cyclomatic complexity of Python functions."""
        findings: list[AgentFinding] = []
        func_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)")

        func_name = ""
        func_start = 0
        func_indent = 0
        complexity = 1  # Base complexity
        in_function = False

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                # Score previous function
                if in_function and complexity > COMPLEXITY_THRESHOLD:
                    level = self._complexity_level(complexity)
                    findings.append(AgentFinding(
                        severity="medium" if complexity <= 20 else "high",
                        description=f"Function '{func_name}' has cyclomatic complexity {complexity} ({level})",
                        file_path=rel_path,
                        line_number=func_start + 1,
                        category="cyclomatic_complexity",
                        solution=f"Reduce complexity of '{func_name}' by extracting conditional branches into helper functions, using early returns, or applying the strategy pattern.",
                        solution_code=f"# Before: complex function with many branches\ndef {func_name}(...):\n    if ...:      # branch 1\n        ...\n    elif ...:    # branch 2\n        ...\n\n# After: extract into focused helpers\ndef {func_name}(...):\n    if _should_handle_case_a(...):\n        return _handle_case_a(...)\n    return _handle_default(...)\n\ndef _handle_case_a(...):\n    ...  # isolated logic",
                        solution_reference="https://refactoring.guru/smells/long-method",
                        fix_difficulty="medium",
                        estimated_fix_minutes=25,
                    ))

                # Start new function
                func_name = match.group(2)
                func_start = i
                func_indent = len(line) - len(line.lstrip())
                complexity = 1
                in_function = True
                continue

            if in_function:
                # Check if we left the function (line at same or lesser indent, non-empty)
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= func_indent and not line.strip().startswith(("@", ")")):
                        # Exited function — score it
                        if complexity > COMPLEXITY_THRESHOLD:
                            level = self._complexity_level(complexity)
                            findings.append(AgentFinding(
                                severity="medium" if complexity <= 20 else "high",
                                description=f"Function '{func_name}' has cyclomatic complexity {complexity} ({level})",
                                file_path=rel_path,
                                line_number=func_start + 1,
                                category="cyclomatic_complexity",
                                solution=f"Reduce complexity of '{func_name}' by extracting conditional branches into helper functions, using early returns, or applying the strategy pattern.",
                                solution_code=f"# Refactor: split complex conditionals into helper functions\ndef {func_name}(...):\n    return _dispatch(...)\n\ndef _dispatch(...):\n    handlers = {{'case_a': _handle_a, 'case_b': _handle_b}}\n    return handlers.get(key, _default)()",
                                fix_difficulty="medium",
                                estimated_fix_minutes=25,
                            ))
                        in_function = False
                        # Check if this line starts a new function
                        new_match = func_pattern.match(line)
                        if new_match:
                            func_name = new_match.group(2)
                            func_start = i
                            func_indent = current_indent
                            complexity = 1
                            in_function = True
                        continue

                # Count complexity contributors
                complexity += len(COMPLEXITY_KEYWORDS.findall(line))

        # Score last function
        if in_function and complexity > COMPLEXITY_THRESHOLD:
            level = self._complexity_level(complexity)
            findings.append(AgentFinding(
                severity="medium" if complexity <= 20 else "high",
                description=f"Function '{func_name}' has cyclomatic complexity {complexity} ({level})",
                file_path=rel_path,
                line_number=func_start + 1,
                category="cyclomatic_complexity",
                solution=f"Reduce complexity of '{func_name}' by extracting branches into helper methods.",
                solution_code=f"# Split '{func_name}' into smaller focused functions\n# Each branch becomes its own well-named function",
                fix_difficulty="medium",
                estimated_fix_minutes=25,
            ))

        return findings

    def _complexity_level(self, complexity: int) -> str:
        if complexity <= 5:
            return "simple"
        elif complexity <= 10:
            return "moderate"
        elif complexity <= 20:
            return "complex"
        else:
            return "very complex"

    def _check_unused_imports(self, content: str, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Detect unused imports in Python files."""
        findings: list[AgentFinding] = []

        import_pattern = re.compile(r"^(?:from\s+[\w.]+\s+)?import\s+(.+)", re.MULTILINE)

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue

            # Extract imported names
            match = import_pattern.match(stripped)
            if not match:
                continue

            imported_part = match.group(1).strip()

            # Handle 'import X as Y' and 'from X import Y, Z'
            names: list[str] = []
            for item in imported_part.split(","):
                item = item.strip()
                if " as " in item:
                    names.append(item.split(" as ")[-1].strip())
                elif item and item != "*":
                    # Handle 'import os.path' -> check for 'os'
                    names.append(item.split(".")[0].strip())

            # Check if each name is used elsewhere in the file (excluding the import line itself)
            remaining_content = "\n".join(lines[:i] + lines[i + 1:])
            for name in names:
                if not name or name.startswith("_"):
                    continue
                # Check if name appears as a word boundary in the rest of the file
                if not re.search(rf"\b{re.escape(name)}\b", remaining_content):
                    findings.append(AgentFinding(
                        severity="low",
                        description=f"Unused import: '{name}'",
                        file_path=rel_path,
                        line_number=i + 1,
                        category="unused_import",
                        solution=f"Remove the unused import '{name}' to keep the code clean and avoid confusion. Unused imports slow down module loading and can mask actual dependencies.",
                        solution_code=f"# Remove this line:\n# {stripped}\n\n# Or if partially unused, keep only what's used:\n# from module import only_used_name",
                        fix_difficulty="easy",
                        estimated_fix_minutes=2,
                    ))

        return findings[:20]  # Limit to 20 to avoid noise

    def _check_magic_numbers(self, lines: list[str], rel_path: str, ext: str) -> list[AgentFinding]:
        """Detect magic numbers (bare numeric literals not 0, 1, -1)."""
        findings: list[AgentFinding] = []
        # Pattern: bare numbers not in assignments, not 0/1/-1
        magic_re = re.compile(r"(?<!=\s)(?<!['\"\w])(-?\d+\.?\d*)(?!['\"\w])")
        # Skip numbers that are allowed
        allowed = {"0", "1", "-1", "0.0", "1.0", "2", "100", "0.5"}
        # Lines that are assignments/constants are OK
        const_line_re = re.compile(r"^\s*[A-Z_]+\s*=|^\s*\w+\s*=\s*-?\d")

        count = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip comments, empty lines, constant definitions
            if not stripped or stripped.startswith(("#", "//", "*", "/*")):
                continue
            if const_line_re.match(stripped):
                continue
            # Skip import lines
            if stripped.startswith(("import ", "from ")):
                continue

            for match in magic_re.finditer(line):
                num = match.group(1)
                if num in allowed:
                    continue
                # Skip if it's part of a range, index, or version string
                if "range(" in line or "version" in line.lower():
                    continue
                count += 1
                if count <= 5:  # Limit findings
                    findings.append(AgentFinding(
                        severity="low",
                        description=f"Magic number {num} — consider extracting to a named constant",
                        file_path=rel_path,
                        line_number=i + 1,
                        category="magic_number",
                        solution=f"Replace magic number {num} with a descriptive constant. Named constants improve readability and make values easy to change.",
                        solution_code=f"# Before (magic number):\n# ... {num} ...\n\n# After (named constant):\nMAX_RETRY_COUNT = {num}  # descriptive name\n# ... MAX_RETRY_COUNT ...",
                        fix_difficulty="easy",
                        estimated_fix_minutes=5,
                    ))

        return findings

    def _check_empty_except(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Detect empty except blocks (bare except or except Exception without handling)."""
        findings: list[AgentFinding] = []
        except_re = re.compile(r"^\s*except\s*(?:Exception)?(?:\s+as\s+\w+)?\s*:")

        for i, line in enumerate(lines):
            if except_re.match(line):
                # Check next lines for actual handling (logging, raise, return)
                has_handling = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith("#"):
                        continue
                    if any(kw in next_line for kw in ("log", "raise", "return", "print", "warn", "error")):
                        has_handling = True
                        break
                    if next_line == "pass":
                        break
                    # If we hit another statement, assume it's handled
                    has_handling = True
                    break

                if not has_handling:
                    findings.append(AgentFinding(
                        severity="medium",
                        description=f"Empty/silent exception handler — errors are swallowed silently",
                        file_path=rel_path,
                        line_number=i + 1,
                        category="empty_except",
                        solution="Never silently swallow exceptions. At minimum, log the error. Prefer catching specific exception types and either handling them properly, re-raising, or logging with traceback.",
                        solution_code="# BAD — silent failure:\ntry:\n    risky_operation()\nexcept Exception:\n    pass\n\n# GOOD — log and handle:\nimport logging\nlogger = logging.getLogger(__name__)\n\ntry:\n    risky_operation()\nexcept SpecificError as e:\n    logger.error(f'Operation failed: {e}', exc_info=True)\n    # handle gracefully or re-raise\n    raise",
                        fix_difficulty="easy",
                        estimated_fix_minutes=10,
                    ))

        return findings

    def _check_python_naming(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Check Python naming conventions: functions=snake_case, classes=PascalCase."""
        findings: list[AgentFinding] = []
        func_re = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)")
        class_re = re.compile(r"^\s*class\s+([a-zA-Z_]\w*)")
        snake_case_re = re.compile(r"^[a-z_][a-z0-9_]*$")
        pascal_case_re = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

        for i, line in enumerate(lines):
            # Check function names
            func_match = func_re.match(line)
            if func_match:
                name = func_match.group(1)
                # Skip dunder methods and private methods
                if name.startswith("__") or name.startswith("_"):
                    continue
                if not snake_case_re.match(name):
                    if len(findings) < 10:
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"Function '{name}' should use snake_case naming",
                            file_path=rel_path,
                            line_number=i + 1,
                            category="naming_convention",
                            solution=f"Rename '{name}' to snake_case. Python PEP 8 convention: functions and variables use lowercase_with_underscores.",
                            solution_code=f"# Before:\ndef {name}(...):\n    ...\n\n# After (snake_case):\ndef {self._to_snake_case(name)}(...):\n    ...",
                            fix_difficulty="easy",
                            estimated_fix_minutes=5,
                        ))

            # Check class names
            class_match = class_re.match(line)
            if class_match:
                name = class_match.group(1)
                if not pascal_case_re.match(name) and not name.startswith("_"):
                    if len(findings) < 10:
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"Class '{name}' should use PascalCase naming",
                            file_path=rel_path,
                            line_number=i + 1,
                            category="naming_convention",
                            solution=f"Rename '{name}' to PascalCase. Python PEP 8 convention: class names use CapWords.",
                            solution_code=f"# Before:\nclass {name}:\n    ...\n\n# After (PascalCase):\nclass {self._to_pascal_case(name)}:\n    ...",
                            fix_difficulty="easy",
                            estimated_fix_minutes=5,
                        ))

        return findings

    def _check_js_naming(self, lines: list[str], rel_path: str) -> list[AgentFinding]:
        """Check JS/TS naming: functions=camelCase, classes/components=PascalCase."""
        findings: list[AgentFinding] = []
        func_re = re.compile(r"(?:function\s+([a-zA-Z_]\w*)|(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\()")
        class_re = re.compile(r"class\s+([a-zA-Z_]\w*)")
        camel_case_re = re.compile(r"^[a-z][a-zA-Z0-9]*$")
        pascal_case_re = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

        for i, line in enumerate(lines):
            # Check function names
            func_match = func_re.search(line)
            if func_match:
                name = func_match.group(1) or func_match.group(2)
                if name and not name.startswith("_"):
                    # Allow PascalCase for React components (arrow function components)
                    if not camel_case_re.match(name) and not pascal_case_re.match(name):
                        if len(findings) < 10:
                            findings.append(AgentFinding(
                                severity="low",
                                description=f"Function '{name}' should use camelCase naming",
                                file_path=rel_path,
                                line_number=i + 1,
                                category="naming_convention",
                                solution=f"Rename '{name}' to camelCase. JavaScript convention: functions and variables use camelCase, classes use PascalCase.",
                                solution_code=f"// Before:\nfunction {name}() {{ ... }}\n\n// After (camelCase):\nfunction {self._to_camel_case(name)}() {{ ... }}",
                                fix_difficulty="easy",
                                estimated_fix_minutes=5,
                            ))

            # Check class names
            class_match = class_re.search(line)
            if class_match:
                name = class_match.group(1)
                if not pascal_case_re.match(name):
                    if len(findings) < 10:
                        findings.append(AgentFinding(
                            severity="low",
                            description=f"Class '{name}' should use PascalCase naming",
                            file_path=rel_path,
                            line_number=i + 1,
                            category="naming_convention",
                            solution=f"Rename '{name}' to PascalCase. JavaScript/TypeScript convention: classes use PascalCase.",
                            solution_code=f"// Before:\nclass {name} {{ ... }}\n\n// After (PascalCase):\nclass {self._to_pascal_case(name)} {{ ... }}",
                            fix_difficulty="easy",
                            estimated_fix_minutes=5,
                        ))

        return findings

    def _detect_long_functions(self, lines: list[str], rel_path: str, ext: str) -> list[AgentFinding]:
        """Detect functions that exceed the line threshold."""
        findings: list[AgentFinding] = []

        if ext == ".py":
            pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)")
        elif ext in {".js", ".ts", ".tsx", ".jsx"}:
            pattern = re.compile(r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)")
        else:
            return findings

        func_start: int | None = None
        func_name: str = ""

        for i, line in enumerate(lines):
            match = pattern.match(line) if ext == ".py" else pattern.search(line)
            if match:
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
                            solution_code=f"# Refactor: split '{func_name}' into focused helpers\ndef {func_name}(...):\n    data = _validate_input(...)\n    result = _process_data(data)\n    return _format_output(result)\n\ndef _validate_input(...):\n    ...\n\ndef _process_data(data):\n    ...",
                            fix_difficulty="medium",
                            estimated_fix_minutes=20,
                        ))

                func_start = i
                groups = match.groups()
                func_name = next((g for g in groups if g and g != "async"), "anonymous")

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
                    solution=f"Break '{func_name}' into smaller functions.",
                    solution_code=f"# Refactor: split '{func_name}' into focused helper functions\n# Each function should be <50 lines and do one thing well.",
                    fix_difficulty="medium",
                    estimated_fix_minutes=20,
                ))

        return findings

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert a name to snake_case."""
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        """Convert a name to PascalCase."""
        return "".join(word.capitalize() for word in re.split(r"[_\-\s]+", name))

    @staticmethod
    def _to_camel_case(name: str) -> str:
        """Convert a name to camelCase."""
        pascal = "".join(word.capitalize() for word in re.split(r"[_\-\s]+", name))
        return pascal[0].lower() + pascal[1:] if pascal else name
