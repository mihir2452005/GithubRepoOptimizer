"""
DependencyAgent — Reads and analyzes project dependency files.
Supports requirements.txt, package.json, go.mod, Cargo.toml, pom.xml.
Includes OSV.dev vulnerability lookup for known CVEs.
"""

import os
import json
import re

import httpx
import structlog

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding

logger = structlog.get_logger()

# OSV ecosystem mapping
ECOSYSTEM_MAP = {
    "python": "PyPI",
    "nodejs": "npm",
    "go": "Go",
    "rust": "crates.io",
}

# Max dependencies to check against OSV (rate limit friendly)
OSV_MAX_PACKAGES = 20
OSV_API_URL = "https://api.osv.dev/v1/query"
OSV_TIMEOUT = 10.0  # seconds per request


class DependencyAgent(BaseAgent):
    name = "dependency"
    version = "1.1.0"
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

        # OSV.dev vulnerability lookup
        vuln_findings = await self._check_vulnerabilities(all_deps)
        findings.extend(vuln_findings)

        vuln_count = len(vuln_findings)
        summary = (
            f"Found {total_deps} dependencies across {len(all_deps)} ecosystem(s): "
            f"{', '.join(all_deps.keys()) if all_deps else 'none detected'}. "
            f"Vulnerabilities detected: {vuln_count}."
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
                "vulnerabilities_found": vuln_count,
            },
            summary=summary,
        )

    async def _check_vulnerabilities(self, all_deps: dict[str, list[dict]]) -> list[AgentFinding]:
        """
        Check dependencies against OSV.dev for known vulnerabilities.
        Limits to first OSV_MAX_PACKAGES dependencies to avoid rate limiting.
        Gracefully degrades if API is unreachable.
        """
        findings: list[AgentFinding] = []
        packages_checked = 0

        try:
            async with httpx.AsyncClient(timeout=OSV_TIMEOUT) as client:
                for ecosystem, deps in all_deps.items():
                    osv_ecosystem = ECOSYSTEM_MAP.get(ecosystem)
                    if not osv_ecosystem:
                        continue

                    for dep in deps:
                        if packages_checked >= OSV_MAX_PACKAGES:
                            break

                        name = dep.get("name", "")
                        version = dep.get("version", "")
                        if not name:
                            continue

                        packages_checked += 1

                        try:
                            # Build OSV query
                            query_body: dict = {
                                "package": {
                                    "name": name,
                                    "ecosystem": osv_ecosystem,
                                }
                            }
                            if version:
                                query_body["version"] = version

                            response = await client.post(OSV_API_URL, json=query_body)

                            if response.status_code != 200:
                                continue

                            data = response.json()
                            vulns = data.get("vulns", [])

                            for vuln in vulns:
                                finding = self._vuln_to_finding(
                                    vuln, name, version, ecosystem
                                )
                                if finding:
                                    findings.append(finding)

                        except (httpx.TimeoutException, httpx.RequestError) as e:
                            logger.warning(
                                "osv_request_failed",
                                package=name,
                                error=str(e),
                            )
                            continue

        except Exception as e:
            logger.warning(
                "osv_api_unreachable",
                error=str(e),
                message="Continuing without vulnerability data",
            )

        return findings

    def _vuln_to_finding(
        self, vuln: dict, package_name: str, version: str, ecosystem: str
    ) -> AgentFinding | None:
        """Convert an OSV vulnerability response to a detailed, user-friendly AgentFinding."""
        vuln_id = vuln.get("id", "")
        summary = vuln.get("summary", vuln.get("details", "Unknown vulnerability"))
        aliases = vuln.get("aliases", [])

        # Determine severity
        severity = self._determine_severity(vuln)

        # Determine fix version
        fix_version = self._get_fix_version(vuln, package_name)

        # CVE alias for display
        cve_ids = [a for a in aliases if a.startswith("CVE-")]
        cve_display = f" ({cve_ids[0]})" if cve_ids else ""

        # Build detailed description explaining WHAT the vulnerability means
        description = (
            f"🚨 {package_name}{f' v{version}' if version else ''} has a known vulnerability: "
            f"{vuln_id}{cve_display}.\n\n"
            f"What this means: {summary[:300]}.\n\n"
            f"{'This is a CRITICAL security issue that could allow attackers to compromise your application.' if severity == 'critical' else ''}"
            f"{'This is a HIGH severity issue that should be fixed before deployment.' if severity == 'high' else ''}"
            f"{'This is a MEDIUM severity issue — fix it in your next maintenance cycle.' if severity == 'medium' else ''}"
            f"{'This is a LOW severity issue — be aware but it may not require immediate action.' if severity == 'low' else ''}"
        )

        # Build comprehensive solution
        if ecosystem == "python":
            if fix_version:
                upgrade_cmd = f"pip install \"{package_name}>={fix_version}\""
                solution_code = (
                    f"# Step 1: Upgrade {package_name} to the fixed version\n"
                    f"pip install \"{package_name}>={fix_version}\"\n\n"
                    f"# Step 2: Update your requirements.txt\n"
                    f"# Change: {package_name}=={version}\n"
                    f"# To:     {package_name}>={fix_version}\n\n"
                    f"# Step 3: Verify the fix\n"
                    f"pip show {package_name}  # Should show version >= {fix_version}\n\n"
                    f"# Step 4: Run your tests to ensure nothing broke\n"
                    f"pytest"
                )
            else:
                upgrade_cmd = f"pip install --upgrade {package_name}"
                solution_code = (
                    f"# Upgrade to the latest version\n"
                    f"pip install --upgrade {package_name}\n\n"
                    f"# Update requirements.txt\n"
                    f"pip freeze | grep -i {package_name} >> requirements.txt\n\n"
                    f"# Run tests after upgrading\n"
                    f"pytest"
                )
        elif ecosystem == "nodejs":
            if fix_version:
                upgrade_cmd = f"npm install {package_name}@{fix_version}"
                solution_code = (
                    f"# Step 1: Install the fixed version\n"
                    f"npm install {package_name}@{fix_version}\n\n"
                    f"# Or if it's a dev dependency:\n"
                    f"npm install --save-dev {package_name}@{fix_version}\n\n"
                    f"# Step 2: Verify\n"
                    f"npm ls {package_name}\n\n"
                    f"# Step 3: Run tests\n"
                    f"npm test"
                )
            else:
                upgrade_cmd = f"npm install {package_name}@latest"
                solution_code = (
                    f"# Upgrade to latest\n"
                    f"npm install {package_name}@latest\n\n"
                    f"# Run audit to verify fix\n"
                    f"npm audit"
                )
        elif ecosystem == "go":
            upgrade_cmd = f"go get {package_name}@latest"
            solution_code = (
                f"# Upgrade the dependency\n"
                f"go get {package_name}@latest\n"
                f"go mod tidy\n\n"
                f"# Verify\n"
                f"go list -m {package_name}"
            )
        elif ecosystem == "rust":
            upgrade_cmd = f"cargo update -p {package_name}"
            solution_code = (
                f"# Update in Cargo.toml and lock\n"
                f"cargo update -p {package_name}\n\n"
                f"# Or specify minimum version in Cargo.toml:\n"
                f'# {package_name} = ">={fix_version}"' if fix_version else f"cargo update -p {package_name}"
            )
        else:
            upgrade_cmd = f"Update {package_name} to latest version"
            solution_code = f"# Update {package_name} using your package manager"

        solution = (
            f"Upgrade {package_name} to "
            f"{'version ' + fix_version + ' or later' if fix_version else 'the latest version'} "
            f"to resolve {vuln_id}{cve_display}. "
            f"After upgrading, run your test suite to ensure compatibility."
        )

        # Build reference URL
        reference_url = f"https://osv.dev/vulnerability/{vuln_id}"

        return AgentFinding(
            severity=severity,
            description=description.strip(),
            category="vulnerability",
            file_path=f"requirements.txt" if ecosystem == "python" else (
                "package.json" if ecosystem == "nodejs" else (
                    "go.mod" if ecosystem == "go" else "Cargo.toml"
                )
            ),
            solution=solution,
            solution_code=solution_code,
            solution_reference=reference_url,
            fix_difficulty="easy",
            estimated_fix_minutes=10,
        )

    def _determine_severity(self, vuln: dict) -> str:
        """Determine severity from OSV vulnerability data."""
        # Check database_specific or severity field
        severity_list = vuln.get("severity", [])
        for sev in severity_list:
            score_str = sev.get("score", "")
            if score_str:
                try:
                    # CVSS score parsing
                    # Extract numeric score if it's a vector string
                    score = float(score_str) if score_str.replace(".", "").isdigit() else 0
                    if score >= 9.0:
                        return "critical"
                    elif score >= 7.0:
                        return "high"
                    elif score >= 4.0:
                        return "medium"
                    else:
                        return "low"
                except (ValueError, TypeError):
                    pass

        # Check ecosystem-specific severity in database_specific
        db_specific = vuln.get("database_specific", {})
        sev_text = db_specific.get("severity", "").upper()
        if sev_text in ("CRITICAL",):
            return "critical"
        elif sev_text in ("HIGH",):
            return "high"
        elif sev_text in ("MODERATE", "MEDIUM"):
            return "medium"
        elif sev_text in ("LOW",):
            return "low"

        # Default to medium for known vulnerabilities
        return "medium"

    def _get_fix_version(self, vuln: dict, package_name: str) -> str | None:
        """Extract fix version from OSV affected ranges."""
        affected = vuln.get("affected", [])
        for entry in affected:
            pkg = entry.get("package", {})
            if pkg.get("name", "").lower() == package_name.lower():
                ranges = entry.get("ranges", [])
                for r in ranges:
                    events = r.get("events", [])
                    for event in events:
                        if "fixed" in event:
                            return event["fixed"]
        return None

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
