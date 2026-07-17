"""
Analysis History — JSON file-based storage for past analysis results.
Gracefully degrades on ephemeral filesystems (e.g., Render free tier).
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


def _get_data_dir() -> str:
    """Determine the data directory, using /tmp on ephemeral deployments."""
    workspace_dir = os.environ.get("WORKSPACE_DIR", "")
    if workspace_dir.startswith("/tmp"):
        # Ephemeral filesystem (e.g., Render) — use /tmp/data
        return "/tmp/data"
    # Default: project-relative data directory
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "data")


DATA_DIR = _get_data_dir()
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


class AnalysisHistory:
    """Persists analysis results to a JSON file for history and diff.
    
    Gracefully handles all file I/O errors — returns empty results
    instead of crashing when history is unavailable.
    """

    def __init__(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(HISTORY_FILE):
                self._write([])
        except (OSError, IOError) as e:
            logger.warning("history_init_failed", error=str(e), data_dir=DATA_DIR)

    def _read(self) -> list[dict]:
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, OSError, IOError) as e:
            logger.warning("history_read_failed", error=str(e))
            return []

    def _write(self, data: list[dict]) -> None:
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except (OSError, IOError) as e:
            logger.warning("history_write_failed", error=str(e))

    def save(self, job_id: str, repo_url: str, results: dict[str, Any],
             optimization_score: int | None = None, health_grade: str | None = None,
             context: dict | None = None) -> dict:
        """Save an analysis result to history. Returns the entry or empty dict on failure."""
        entry = {
            "id": job_id,
            "repo_url": repo_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "optimization_score": optimization_score,
            "health_grade": health_grade,
            "findings_count": sum(
                len(r.get("findings", [])) for r in results.values()
            ),
            "context": context or {},
            "results": results,
        }
        try:
            history = self._read()
            history.insert(0, entry)  # Most recent first
            # Keep last 100 entries
            history = history[:100]
            self._write(history)
        except Exception as e:
            logger.warning("history_save_failed", job_id=job_id, error=str(e))
        return entry

    def get_all(self) -> list[dict]:
        """Get all history entries (summary only, no full results)."""
        history = self._read()
        return [
            {
                "id": h["id"],
                "repo_url": h["repo_url"],
                "timestamp": h["timestamp"],
                "optimization_score": h.get("optimization_score"),
                "health_grade": h.get("health_grade"),
                "findings_count": h.get("findings_count", 0),
            }
            for h in history
        ]

    def get_by_id(self, job_id: str) -> dict | None:
        """Get full results for a specific job."""
        history = self._read()
        for entry in history:
            if entry["id"] == job_id:
                return entry
        return None

    def get_by_repo(self, repo_url: str) -> list[dict]:
        """Get all analyses for a specific repo URL."""
        history = self._read()
        return [
            h for h in history
            if h["repo_url"] == repo_url
        ]


# Singleton
history_store = AnalysisHistory()


def get_history() -> AnalysisHistory:
    """Get the history store singleton."""
    return history_store
