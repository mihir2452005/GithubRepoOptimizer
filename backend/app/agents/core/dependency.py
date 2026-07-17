"""
DependencyAgent — Reads and analyzes project dependency files.
Supports requirements.txt, package.json, go.mod, Cargo.toml, pom.xml.
"""

import os
import json
import re

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class DependencyAgent(BaseAgent):
    name = "dependency"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        findings: list[AgentFinding] = []
        all_deps: dict[str, list[dict]] = {}

        # Check various dependency files
        dep_results = [
            self._parse_requirements_txt(repo_path),
            self._parse_package_json(repo_path),
            self._parse_go_mod(repo_path),
            self._parse_cargo_toml(repo_path),
        ]

        for ecosystem, deps in dep_results:
            if deps:
                all_deps[ecosystem] = deps

        # Generate findings
        total_deps = sum(len(d) for d in all_deps.values())

        if total_deps > 50:
            findings.append(AgentFinding(
                severity="medium",
                description=f"Project has {total_deps} dependencies. Consider reducing dependency count.",
                category="dependency_bloat",
                fix_difficulty="hard",
                estimated_fix_minutes=60,
            ))

        # Check for unpinned dependencies
        for ecosystem, deps in all_deps.items():
            unpinned = [d for d in deps if not d.get("pinned")]
            if unpinned:
                findings.append(AgentFinding(
                    severity="medium",
                    description=f"{len(unpinned)} unpinned dependencies in {ecosystem}. Pin versions for reproducible builds.",
                    category="unpinned_dependency",
                    fix_difficulty="easy",
                    estimated_fix_minutes=15,
                ))

        summary = (
            f"Found {total_deps} dependencies across {len(all_deps)} ecosystem(s): "
            f"{', '.join(all_deps.keys()) if all_deps else 'none detected'}"
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics={
                "total_dependencies": total_deps,
                "ecosystems": list(all_deps.keys()),
                "dependencies_by_ecosystem": {k: len(v) for k, v in all_deps.items()},
                "dependency_list": all_deps,
            },
            summary=summary,
        )

    def _parse_requirements_txt(self, repo_path: str) -> tuple[str, list[dict]]:
        """Parse Python requirements.txt."""
        filepath = os.path.join(repo_path, "requirements.txt")
        if not os.path.isfile(filepath):
            return ("python", [])

        deps = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # Parse name==version or name>=version
                    match = re.match(r"^([\w\-\[\]]+)\s*([>=<!=~]+)?\s*([\w\.\-\*]*)", line)
                    if match:
                        name = match.group(1)
                        operator = match.group(2) or ""
                        version = match.group(3) or ""
                        deps.append({
                            "name": name,
                            "version": version,
                            "operator": operator,
                            "pinned": operator == "==",
                        })
        except OSError:
            pass

        return ("python", deps)

    def _parse_package_json(self, repo_path: str) -> tuple[str, list[dict]]:
        """Parse Node.js package.json."""
        filepath = os.path.join(repo_path, "package.json")
        if not os.path.isfile(filepath):
            return ("nodejs", [])

        deps = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                pkg = json.load(f)

            for section in ("dependencies", "devDependencies"):
                for name, version in pkg.get(section, {}).items():
                    pinned = not any(c in version for c in "^~*>< ")
                    deps.append({
                        "name": name,
                        "version": version,
                        "section": section,
                        "pinned": pinned,
                    })
        except (OSError, json.JSONDecodeError):
            pass

        return ("nodejs", deps)

    def _parse_go_mod(self, repo_path: str) -> tuple[str, list[dict]]:
        """Parse Go go.mod."""
        filepath = os.path.join(repo_path, "go.mod")
        if not os.path.isfile(filepath):
            return ("go", [])

        deps = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                in_require = False
                for line in f:
                    line = line.strip()
                    if line.startswith("require ("):
                        in_require = True
                        continue
                    if line == ")":
                        in_require = False
                        continue
                    if in_require and line:
                        parts = line.split()
                        if len(parts) >= 2:
                            deps.append({
                                "name": parts[0],
                                "version": parts[1],
                                "pinned": True,
                            })
        except OSError:
            pass

        return ("go", deps)

    def _parse_cargo_toml(self, repo_path: str) -> tuple[str, list[dict]]:
        """Parse Rust Cargo.toml (basic parsing)."""
        filepath = os.path.join(repo_path, "Cargo.toml")
        if not os.path.isfile(filepath):
            return ("rust", [])

        deps = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                in_deps = False
                for line in f:
                    line = line.strip()
                    if line in ("[dependencies]", "[dev-dependencies]"):
                        in_deps = True
                        continue
                    if line.startswith("[") and in_deps:
                        in_deps = False
                        continue
                    if in_deps and "=" in line:
                        parts = line.split("=", 1)
                        name = parts[0].strip()
                        version = parts[1].strip().strip('"').strip("'")
                        deps.append({
                            "name": name,
                            "version": version,
                            "pinned": not version.startswith("^"),
                        })
        except OSError:
            pass

        return ("rust", deps)
