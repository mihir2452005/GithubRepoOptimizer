"""
RepositoryUnderstandingAgent — Extracts core repo metrics using GitPython.
Language distribution, file count, directory structure, commits, contributors.
"""

import os
from git import Repo, InvalidGitRepositoryError

from ..base import BaseAgent
from ..payloads import AgentInputPayload, AgentOutputPayload, AgentFinding


class RepositoryUnderstandingAgent(BaseAgent):
    name = "repository_understanding"
    version = "1.0.0"
    dependencies = []

    async def run(self, payload: AgentInputPayload) -> AgentOutputPayload:
        repo_path = payload.repo_path
        metrics: dict = {}
        findings: list[AgentFinding] = []

        # Count files by extension
        language_dist: dict[str, int] = {}
        total_files = 0
        total_dirs = 0

        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            total_dirs += len(dirs)
            for f in files:
                total_files += 1
                _, ext = os.path.splitext(f)
                if ext:
                    language_dist[ext.lower()] = language_dist.get(ext.lower(), 0) + 1

        metrics["total_files"] = total_files
        metrics["total_directories"] = total_dirs
        metrics["language_distribution"] = language_dist

        # Git-specific metrics
        try:
            repo = Repo(repo_path)
            commits = list(repo.iter_commits(max_count=1000))
            metrics["total_commits"] = len(commits)

            contributors = set()
            for commit in commits:
                if commit.author:
                    contributors.add(commit.author.email)
            metrics["contributor_count"] = len(contributors)

            # Active branch
            try:
                metrics["active_branch"] = str(repo.active_branch)
            except TypeError:
                metrics["active_branch"] = "detached HEAD"

            # Latest commit
            if commits:
                metrics["latest_commit_sha"] = commits[0].hexsha[:8]
                metrics["latest_commit_message"] = commits[0].message.strip()[:100]

        except (InvalidGitRepositoryError, Exception):
            metrics["total_commits"] = 0
            metrics["contributor_count"] = 0
            findings.append(AgentFinding(
                severity="info",
                description="Repository is not a valid Git repository or has no commits",
                category="repository",
            ))

        # Generate findings for repo health
        if total_files > 1000:
            findings.append(AgentFinding(
                severity="info",
                description=f"Large repository with {total_files} files. Consider modularization.",
                category="repository_size",
            ))

        summary = (
            f"Repository contains {total_files} files across {total_dirs} directories. "
            f"Top languages: {', '.join(sorted(language_dist, key=language_dist.get, reverse=True)[:5])}"
        )

        return AgentOutputPayload(
            agent=self.name,
            status="success",
            findings=findings,
            metrics=metrics,
            summary=summary,
        )
