"""
SharedAnalysisContext — Pre-computed repo metadata shared across all agents.
Built once per job to avoid redundant file-tree walks.
"""

import os
from dataclasses import dataclass, field

# Extension -> language mapping for MVP
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".r": "R",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".md": "Markdown",
    ".sh": "Shell",
    ".bash": "Shell",
    ".dockerfile": "Dockerfile",
}

# Directories to skip during file tree walking
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".nuxt",
    "target", "vendor", ".idea", ".vscode",
}


@dataclass
class SharedAnalysisContext:
    """Pre-computed repository metadata shared across all agents."""

    job_id: str
    repo_path: str
    commit_sha: str = ""
    branch: str = ""
    language_map: dict[str, list[str]] = field(default_factory=dict)
    file_index: dict[str, dict] = field(default_factory=dict)
    framework_detection: str | None = None


class SharedAnalysisContextBuilder:
    """Builds SharedAnalysisContext by walking the repo file tree."""

    def build(self, job_id: str, repo_path: str) -> SharedAnalysisContext:
        """
        Build context by walking the file tree.
        Detects languages by extension, indexes files with metadata.
        """
        context = SharedAnalysisContext(job_id=job_id, repo_path=repo_path)
        language_map: dict[str, list[str]] = {}
        file_index: dict[str, dict] = {}

        if not os.path.isdir(repo_path):
            return context

        for root, dirs, files in os.walk(repo_path):
            # Skip ignored directories in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)

                # Detect language from extension
                _, ext = os.path.splitext(filename)
                ext_lower = ext.lower()
                language = EXTENSION_LANGUAGE_MAP.get(ext_lower, "Unknown")

                # Get file size
                try:
                    size_bytes = os.path.getsize(filepath)
                except OSError:
                    size_bytes = 0

                # Index the file
                file_index[rel_path] = {
                    "language": language,
                    "size_bytes": size_bytes,
                    "parse_error": None,
                }

                # Map language -> files
                if language != "Unknown":
                    if language not in language_map:
                        language_map[language] = []
                    language_map[language].append(rel_path)

        context.language_map = language_map
        context.file_index = file_index

        # Simple framework detection
        context.framework_detection = self._detect_framework(repo_path, file_index)

        return context

    def _detect_framework(self, repo_path: str, file_index: dict) -> str | None:
        """Simple framework detection based on file presence."""
        files = set(file_index.keys())

        if "package.json" in files:
            pkg_path = os.path.join(repo_path, "package.json")
            try:
                import json
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    return "Next.js"
                if "react" in deps:
                    return "React"
                if "vue" in deps:
                    return "Vue"
                if "express" in deps:
                    return "Express"
                return "Node.js"
            except (json.JSONDecodeError, OSError):
                return "Node.js"

        if "requirements.txt" in files or "pyproject.toml" in files:
            if "manage.py" in files:
                return "Django"
            if any("flask" in f.lower() for f in files):
                return "Flask"
            return "Python"

        if "go.mod" in files:
            return "Go"

        if "Cargo.toml" in files:
            return "Rust"

        if "pom.xml" in files or "build.gradle" in files:
            return "Java/JVM"

        return None
