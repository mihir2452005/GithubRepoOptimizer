"""
ArchitectureAgent — Analyzes import structure and architectural patterns.
Detects circular imports, identifies entry points, maps dependencies.
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


class ArchitectureAgent(BaseAgent):
    name = "architecture"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []

        # Build import graph for Python files
        import_graph = self._build_python_import_graph(repo_path)

        # Detect circular imports
        cycles = self._find_cycles(import_graph)
        for cycle in cycles[:10]:  # Limit to top 10
            cycle_str = ' → '.join(cycle)
            findings.append(AgentFinding(
                severity="high",
                description=f"Circular import detected: {cycle_str}",
                category="circular_import",
                solution=f"Break the circular dependency between {cycle[0]} and {cycle[-2]}. Common fixes: 1) Move shared code to a new module both can import, 2) Use dependency injection, 3) Use lazy imports (import inside function), 4) Merge the two modules if they're tightly coupled.",
                solution_code=f"# Option 1: Lazy import (quick fix)\ndef my_function():\n    from {cycle[-2]} import needed_class  # import inside function\n    ...\n\n# Option 2: Extract shared interface\n# Create a new module '{cycle[0]}_interface.py' with shared types\n# Both modules import from the interface instead of each other",
                solution_reference="https://refactoring.guru/smells/shotgun-surgery",
                fix_difficulty="medium",
                estimated_fix_minutes=30,
            ))

        # Identify entry points
        entry_points = self._find_entry_points(repo_path)

        # Detect lack of layering
        if len(import_graph) > 20 and not cycles:
            # Large project without clear layer violations is good
            findings.append(AgentFinding(
                severity="info",
                description="No circular dependencies detected in import graph",
                category="architecture_health",
            ))

        metrics = {
            "modules_analyzed": len(import_graph),
            "total_imports": sum(len(v) for v in import_graph.values()),
            "circular_dependencies": len(cycles),
            "entry_points": entry_points,
        }

        summary = (
            f"Analyzed {len(import_graph)} modules. "
            f"Found {len(cycles)} circular dependencies. "
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

                # Extract imports
                imports = set()
                for match in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
                    imports.add(match.group(1))
                for match in re.finditer(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE):
                    imports.add(match.group(1))

                graph[module_name] = imports

        return graph

    def _find_cycles(self, graph: dict[str, set[str]]) -> list[list[str]]:
        """Find circular dependencies using DFS."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []
        on_path: set[str] = set()

        def dfs(node: str) -> None:
            if len(cycles) >= 10:  # Limit search
                return
            if node in on_path:
                # Found a cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return

            visited.add(node)
            on_path.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor in graph:  # Only follow internal modules
                    dfs(neighbor)

            path.pop()
            on_path.remove(node)

        for node in list(graph.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    def _find_entry_points(self, repo_path: str) -> list[str]:
        """Identify likely entry points in the repository."""
        entry_points: list[str] = []
        entry_patterns = [
            "main.py", "app.py", "server.py", "index.py",
            "manage.py", "wsgi.py", "asgi.py",
            "index.js", "index.ts", "main.js", "main.ts",
            "server.js", "server.ts", "app.js", "app.ts",
            "main.go", "cmd",
        ]

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                if filename in entry_patterns:
                    rel_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    entry_points.append(rel_path)

        return entry_points
