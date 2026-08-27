"""Read-only, size-bounded tools exposed to the investigation agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fixtrace.core.models import AgentObservation, Evidence
from fixtrace.services.redactor import SecretRedactor

_IGNORED = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}


class AgentTools:
    def __init__(
        self,
        root: Path,
        evidence: list[Evidence],
        *,
        max_output_chars: int,
        redactor: SecretRedactor,
    ) -> None:
        self.root = root.resolve()
        self.evidence = evidence
        self.max_output_chars = max_output_chars
        self.redactor = redactor

    def execute(
        self,
        observation_id: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> AgentObservation:
        try:
            if tool == "inspect_evidence":
                detail = self._inspect_evidence(arguments)
            elif tool == "list_files":
                detail = self._list_files(arguments)
            elif tool == "search_source":
                detail = self._search_source(arguments)
            elif tool == "read_source":
                detail = self._read_source(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool}")
            clean = self.redactor.redact(detail).text[: self.max_output_chars]
            return AgentObservation(
                id=observation_id,
                tool=tool,
                summary=f"{tool} completed with {len(clean)} characters of output.",
                detail=clean,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            clean_error = self.redactor.redact(str(exc)).text[:500]
            return AgentObservation(
                id=observation_id,
                tool=tool,
                ok=False,
                summary=f"{tool} was rejected or failed.",
                detail=clean_error,
            )

    def _inspect_evidence(self, arguments: dict[str, Any]) -> str:
        requested = arguments.get("evidence_ids", [])
        if requested and not isinstance(requested, list):
            raise ValueError("evidence_ids must be a list.")
        selected = self.evidence
        if requested:
            allowed = {str(item) for item in requested[:30]}
            selected = [item for item in self.evidence if item.id in allowed]
        return json.dumps(
            [item.model_dump(mode="json") for item in selected],
            ensure_ascii=False,
            indent=2,
        )

    def _list_files(self, arguments: dict[str, Any]) -> str:
        start = self._resolve(str(arguments.get("path", ".")), require_file=False)
        if not start.is_dir():
            raise ValueError("list_files path must be a directory.")
        max_depth = _bounded_int(arguments.get("max_depth", 3), 1, 6)
        files: list[str] = []
        visited_directories = 0
        for current, directories, names in os.walk(start, followlinks=False):
            visited_directories += 1
            if visited_directories > 500:
                return "\n".join(files) + "\n[truncated after 500 directories]"
            current_path = Path(current)
            depth = len(current_path.relative_to(start).parts)
            directories[:] = sorted(
                name
                for name in directories
                if name not in _IGNORED and depth < max_depth
            )
            for name in sorted(names):
                path = current_path / name
                if path.is_symlink() or name in _IGNORED:
                    continue
                files.append(path.relative_to(self.root).as_posix())
                if len(files) >= 120:
                    return "\n".join(files) + "\n[truncated at 120 files]"
        return "\n".join(files) if files else "[no files]"

    def _search_source(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        if not 2 <= len(query) <= 160:
            raise ValueError("query must contain 2 to 160 characters.")
        start = self._resolve(str(arguments.get("path", ".")), require_file=False)
        max_results = _bounded_int(arguments.get("max_results", 20), 1, 40)
        candidates = [start] if start.is_file() else self._iter_files(start)
        hits: list[str] = []
        lowered = query.casefold()
        scanned_bytes = 0
        for path in candidates:
            if not self._is_readable_source(path):
                continue
            try:
                scanned_bytes += path.stat().st_size
                if scanned_bytes > 25_000_000:
                    return "\n".join(hits) + "\n[search stopped at 25 MB]"
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
                ):
                    if lowered in line.casefold():
                        relative = path.relative_to(self.root).as_posix()
                        hits.append(f"{relative}:{line_number}: {line[:300]}")
                        if len(hits) >= max_results:
                            return "\n".join(hits)
            except OSError:
                continue
        return "\n".join(hits) if hits else "[no matches]"

    def _read_source(self, arguments: dict[str, Any]) -> str:
        raw_path = str(arguments.get("path", "")).strip()
        if not raw_path:
            raise ValueError("path is required.")
        path = self._resolve(raw_path, require_file=True)
        if not self._is_readable_source(path):
            raise ValueError("File is too large, binary, ignored, or unavailable.")
        start_line = _bounded_int(arguments.get("start_line", 1), 1, 1_000_000)
        end_line = _bounded_int(
            arguments.get("end_line", start_line + 119), start_line, start_line + 199
        )
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : end_line]
        return "\n".join(
            f"{number}: {line}"
            for number, line in enumerate(selected, start=start_line)
        ) or "[requested range is empty]"

    def _resolve(self, raw_path: str, *, require_file: bool) -> Path:
        candidate = (self.root / raw_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path escapes the prepared repository.")
        relative_parts = candidate.relative_to(self.root).parts
        if any(part in _IGNORED for part in relative_parts):
            raise ValueError("Path targets an ignored directory.")
        if not candidate.exists():
            raise ValueError("Path does not exist in the prepared repository.")
        if require_file and not candidate.is_file():
            raise ValueError("Path must identify a file.")
        return candidate

    def _iter_files(self, start: Path) -> list[Path]:
        files: list[Path] = []
        for current, directories, names in os.walk(start, followlinks=False):
            directories[:] = sorted(name for name in directories if name not in _IGNORED)
            for name in sorted(names):
                path = Path(current) / name
                if not path.is_symlink():
                    files.append(path)
                if len(files) >= 2_000:
                    return files
        return files

    @staticmethod
    def _is_readable_source(path: Path) -> bool:
        try:
            if not path.is_file() or path.stat().st_size > 750_000:
                return False
            sample = path.read_bytes()[:2048]
        except OSError:
            return False
        return b"\x00" not in sample


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected an integer argument.") from exc
    return max(minimum, min(maximum, parsed))
