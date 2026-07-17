"""
ArchitectureAgent — Analyzes import structure, architectural patterns,
module coupling, and supports Python + JS/TS codebases.
Detects circular imports, god modules, and common architectural patterns.
"""

import os
import re
from collections import defaultdict

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", "vendor", ".next", "target",
}

# Entry point filenames for different ecosystems
PYTHON_ENTRY_POINTS = {"main.py", "app.py", "server.py", "wsgi.py", "asgi.py", "manage.py", "index.py"}
JS_TS_ENTRY_POINTS = {"index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts", "server.js", "server.ts"}

# Architectural pattern indicators
PATTERN_INDICATORS = {
    "mvc": {"models", "views", "controllers", "routes"},
    "layered": {"services", "repositories", "dal"},
    "component_based": {"components"},
    "microservices_docker": set(),  # detected by multiple Dockerfiles
}


class ArchitectureAgent(BaseAgent):
    name = "architecture"
    version = "2.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []

        # Build import graphs for Python and JS/TS files
        python_graph = self._build_python_import_graph(repo_path)
        js_graph = self._build_js_import_graph(repo_path)

        # Merge graphs for combined analysis
        combined_graph: dict[str, set[str]] = defaultdict(set)
        for k, v in python_graph.items():
            combined_graph[k] = v
        for k, v in js_graph.items():
            combined_graph[k] = v

        # Detect circular imports (Python)
        cycles = self._find_cycles(python_graph)
        for cycle in cycles[:10]:
            cycle_str = " → ".join(cycle)
            findings.append(AgentFinding(
                severity="high",
                description=f"Circular import detected: {cycle_str}",
                category="circular_import",
                solution=f"Break the circular dependency between {cycle[0]} and {cycle[-2]}. Common fixes: 1) Move shared code to a new module, 2) Use dependency injection, 3) Use lazy imports inside functions, 4) Merge tightly coupled modules.",
                solution_code=f"# Option 1: Lazy import (quick fix)\ndef my_function():\n    from {cycle[-2]} import needed_class  # import inside function\n    ...\n\n# Option 2: Extract shared interface\n# Create '{cycle[0]}_interface.py' with shared types\n# Both modules import from the interface instead of each other",
                solution_reference="https://refactoring.guru/smells/shotgun-surgery",
                fix_difficulty="medium",
                estimated_fix_minutes=30,
            ))

        # Detect circular imports (JS/TS)
        js_cycles = self._find_cycles(js_graph)
        for cycle in js_cycles[:10]:
            cycle_str = " → ".join(cycle)
            findings.append(AgentFinding(
                severity="high",
                description=f"Circular import detected (JS/TS): {cycle_str}",
                category="circular_import",
                solution=f"Break this circular dependency. In JS/TS, circular imports can cause undefined values at runtime. Extract shared code to a separate module or use dynamic imports.",
                solution_code=f"// Option 1: Extract shared types to a separate file\n// shared-types.ts — both modules import from here\n\n// Option 2: Dynamic import (breaks the cycle)\nconst module = await import('./{cycle[-2]}');\n\n// Option 3: Dependency injection\n// Pass the dependency as a parameter instead of importing",
                solution_reference="https://nodejs.org/api/modules.html#cycles",
                fix_difficulty="medium",
                estimated_fix_minutes=30,
            ))

        # Detect architectural patterns
        detected_patterns = self._detect_patterns(repo_path)

        # Module coupling analysis
        fan_in = self._compute_fan_in(combined_graph)
        god_modules = [(mod, count) for mod, count in fan_in.items() if count > 10]
        god_modules.sort(key=lambda x: -x[1])

        for mod, count in god_modules[:5]:
            findings.append(AgentFinding(
                severity="medium",
                description=f"God module detected: '{mod}' is imported by {count} other modules (fan-in > 10)",
                file_path=mod.replace(".", os.sep) + ".py" if not mod.endswith((".js", ".ts")) else mod,
                category="high_coupling",
                solution=f"'{mod}' has too many dependents ({count}). Split it into smaller, focused modules. Extract distinct responsibilities into separate files to reduce coupling and improve maintainability.",
                solution_code=f"# Current: {mod} does everything\n# Split into focused modules:\n#\n# {mod}_models.py    — data structures/types\n# {mod}_utils.py     — utility/helper functions\n# {mod}_services.py  — business logic\n#\n# Update imports in dependent modules:\n# from {mod}_models import MyModel\n# from {mod}_services import my_service",
                solution_reference="https://refactoring.guru/smells/large-class",
                fix_difficulty="hard",
                estimated_fix_minutes=60,
            ))

        # Identify entry points
        entry_points = self._find_entry_points(repo_path)

        metrics = {
            "modules_analyzed": len(combined_graph),
            "python_modules": len(python_graph),
            "js_ts_modules": len(js_graph),
            "total_imports": sum(len(v) for v in combined_graph.values()),
            "circular_dependencies": len(cycles) + len(js_cycles),
            "detected_patterns": detected_patterns,
            "god_modules": [{"module": m, "fan_in": c} for m, c in god_modules[:5]],
            "entry_points": entry_points,
            "average_fan_in": round(sum(fan_in.values()) / max(len(fan_in), 1), 2),
        }

        summary = (
            f"Analyzed {len(combined_graph)} modules ({len(python_graph)} Python, {len(js_graph)} JS/TS). "
            f"Found {len(cycles) + len(js_cycles)} circular dependencies. "
            f"Detected patterns: {', '.join(detected_patterns) if detected_patterns else 'none'}. "
            f"God modules: {len(god_modules)}. "
            f"Entry points: {', '.join(entry_points[:5]) if entry_points else 'none detected'}"
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics=metrics,
            summary=summary,
        )

    def _build_python_import_graph(self, repo_path: str) -> dict[str, set[str]]:
        """Build a module dependency graph from Python imports."""
        graph: dict[str, set[str]] = defaultdict(set)

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)
                module_name = rel_path.replace(os.sep, ".").removesuffix(".py")

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue

                imports = set()
                for match in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
                    imports.add(match.group(1))
                for match in re.finditer(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE):
                    imports.add(match.group(1))

                graph[module_name] = imports

        return graph

    def _build_js_import_graph(self, repo_path: str) -> dict[str, set[str]]:
        """Build a module dependency graph from JS/TS imports."""
        graph: dict[str, set[str]] = defaultdict(set)

        # ES module import pattern: import ... from '...'
        es_import_re = re.compile(r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\))""")
        # CommonJS require pattern: require('...')
        require_re = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except (OSError, UnicodeDecodeError):
                    continue

                imports = set()

                # ES imports
                for match in es_import_re.finditer(content):
                    imp = match.group(1) or match.group(2)
                    if imp and imp.startswith("."):
                        # Resolve relative import to a module path
                        resolved = self._resolve_js_import(rel_path, imp)
                        imports.add(resolved)
                    else:
                        imports.add(imp or "")

                # CommonJS requires
                for match in require_re.finditer(content):
                    imp = match.group(1)
                    if imp.startswith("."):
                        resolved = self._resolve_js_import(rel_path, imp)
                        imports.add(resolved)
                    else:
                        imports.add(imp)

                if imports:
                    graph[rel_path] = imports

        return graph

    def _resolve_js_import(self, source_file: str, import_path: str) -> str:
        """Resolve a relative JS/TS import path to a normalized module path."""
        source_dir = os.path.dirname(source_file)
        resolved = os.path.normpath(os.path.join(source_dir, import_path))
        return resolved.replace(os.sep, "/")

    def _find_cycles(self, graph: dict[str, set[str]]) -> list[list[str]]:
        """Find circular dependencies using DFS."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []
        on_path: set[str] = set()

        def dfs(node: str) -> None:
            if len(cycles) >= 10:
                return
            if node in on_path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return

            visited.add(node)
            on_path.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor in graph:
                    dfs(neighbor)

            path.pop()
            on_path.remove(node)

        for node in list(graph.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    def _compute_fan_in(self, graph: dict[str, set[str]]) -> dict[str, int]:
        """Compute fan-in (how many modules import each module)."""
        fan_in: dict[str, int] = defaultdict(int)

        for module, imports in graph.items():
            for imp in imports:
                # Only count internal modules
                if imp in graph:
                    fan_in[imp] += 1

        return dict(fan_in)

    def _detect_patterns(self, repo_path: str) -> list[str]:
        """Detect architectural patterns based on directory structure."""
        patterns: list[str] = []
        top_dirs: set[str] = set()
        dockerfile_count = 0

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rel_root = os.path.relpath(root, repo_path)
            depth = rel_root.count(os.sep) if rel_root != "." else 0

            # Collect top-level and second-level directory names
            if depth <= 1:
                for d in dirs:
                    top_dirs.add(d.lower())

            # Count Dockerfiles
            for f in files:
                if f.lower() in ("dockerfile", "docker-compose.yml", "docker-compose.yaml"):
                    dockerfile_count += 1

        # MVC: has models/ + views/ + controllers/ (or routes/)
        if ("models" in top_dirs and "views" in top_dirs and
                ("controllers" in top_dirs or "routes" in top_dirs)):
            patterns.append("MVC")

        # Layered: has services/ + repositories/ (or dal/)
        if "services" in top_dirs and ("repositories" in top_dirs or "dal" in top_dirs):
            patterns.append("Layered Architecture")

        # Component-based: has components/ (React/Vue/Angular)
        if "components" in top_dirs:
            patterns.append("Component-Based")

        # Microservices: multiple Dockerfiles or service directories
        if dockerfile_count >= 3:
            patterns.append("Microservices")

        return patterns

    def _find_entry_points(self, repo_path: str) -> list[str]:
        """Identify likely entry points in the repository."""
        entry_points: list[str] = []
        all_entry_names = PYTHON_ENTRY_POINTS | JS_TS_ENTRY_POINTS

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                if filename in all_entry_names:
                    rel_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    entry_points.append(rel_path)

        return entry_points
