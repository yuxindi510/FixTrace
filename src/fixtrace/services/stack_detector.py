"""Technology-stack detection using repository manifests and file signals."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from fixtrace.core.models import StackProfile

_EXCLUDED_DIRS = {
    ".git",
    ".fixtrace",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "venv",
}
_LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}
_MANIFESTS = (
    "Cargo.toml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
)


class StackDetector:
    def detect(self, root: Path) -> StackProfile:
        counts: Counter[str] = Counter()
        scanned = 0
        for path in root.rglob("*"):
            if scanned >= 50_000:
                break
            relative_parts = path.relative_to(root).parts
            if not path.is_file() or any(part in _EXCLUDED_DIRS for part in relative_parts):
                continue
            scanned += 1
            language = _LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
            if language:
                counts[language] += 1

        manifests = [name for name in _MANIFESTS if (root / name).is_file()]
        languages = [name for name, _ in counts.most_common()]
        primary = languages[0] if languages else "unknown"
        frameworks: list[str] = []
        test_command: list[str] | None = None

        dependency_text = self._dependency_text(root, manifests)
        if "pytest" in dependency_text or (root / "pytest.ini").is_file():
            frameworks.append("pytest")
            test_command = [sys.executable, "-m", "pytest", "-q"]
        if "fastapi" in dependency_text:
            frameworks.append("FastAPI")
        if "django" in dependency_text:
            frameworks.append("Django")
        if "flask" in dependency_text:
            frameworks.append("Flask")
        if "react" in dependency_text:
            frameworks.append("React")
        if "vitest" in dependency_text:
            frameworks.append("Vitest")
        if "jest" in dependency_text:
            frameworks.append("Jest")

        strongest_count = counts.most_common(1)[0][1] if counts else 0
        total = sum(counts.values())
        confidence = min(1.0, 0.45 + (strongest_count / total * 0.45)) if total else 0.0
        if manifests:
            confidence = min(1.0, confidence + 0.1)

        return StackProfile(
            primary_language=primary,
            languages=languages[:8],
            frameworks=frameworks,
            manifests=manifests,
            test_command=test_command,
            confidence=round(confidence, 2),
        )

    @staticmethod
    def _dependency_text(root: Path, manifests: list[str]) -> str:
        chunks: list[str] = []
        for name in manifests:
            path = root / name
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore")[:200_000].lower())
            except OSError:
                continue
        return "\n".join(chunks)
