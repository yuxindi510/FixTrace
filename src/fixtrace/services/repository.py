"""Safe-ish repository source validation and temporary checkout management."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_GITHUB_URL = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
_IGNORED_NAMES = {
    ".git",
    ".fixtrace",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


class RepositorySourceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Checkout:
    path: Path
    source_kind: Literal["local", "github", "log"]
    display_name: str


class RepositoryManager:
    def __init__(self, work_root: Path, *, allow_local_sources: bool) -> None:
        self.work_root = work_root.expanduser().resolve()
        self.allow_local_sources = allow_local_sources

    @contextmanager
    def prepare(self, source: str | None, *, isolated: bool) -> Iterator[Checkout]:
        if not source:
            with self._temporary_directory() as temp:
                destination = temp / "log-input"
                destination.mkdir()
                yield Checkout(destination, "log", "log-only analysis")
                return

        local_path = Path(source).expanduser()
        if local_path.exists():
            if not self.allow_local_sources:
                raise RepositorySourceError(
                    "Local repository paths are disabled for the web service. "
                    "Set FIXTRACE_ALLOW_LOCAL_SOURCES=1 only on a trusted local deployment."
                )
            resolved = local_path.resolve()
            if not resolved.is_dir():
                raise RepositorySourceError("Local repository source must be a directory.")
            if not isolated:
                yield Checkout(resolved, "local", resolved.name)
                return
            with self._temporary_directory() as temp:
                destination = temp / resolved.name
                shutil.copytree(
                    resolved,
                    destination,
                    ignore=shutil.ignore_patterns(*sorted(_IGNORED_NAMES)),
                    symlinks=True,
                )
                yield Checkout(destination, "local", resolved.name)
                return

        match = _GITHUB_URL.fullmatch(source.strip())
        if not match:
            raise RepositorySourceError(
                "Repository must be an existing local directory or a public "
                "https://github.com/owner/repository URL."
            )

        owner = match.group("owner")
        repository = match.group("repo")
        canonical_url = f"https://github.com/{owner}/{repository}.git"
        with self._temporary_directory() as temp:
            destination = temp / repository
            try:
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--single-branch",
                        "--",
                        canonical_url,
                        str(destination),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except FileNotFoundError as exc:
                raise RepositorySourceError(
                    "git is required to clone GitHub repositories."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise RepositorySourceError("GitHub clone timed out after 60 seconds.") from exc
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "clone failed").strip().splitlines()[-1]
                raise RepositorySourceError(f"Unable to clone public repository: {detail}") from exc
            yield Checkout(destination, "github", f"{owner}/{repository}")

    @contextmanager
    def _temporary_directory(self) -> Iterator[Path]:
        self.work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="run-", dir=self.work_root) as directory:
            yield Path(directory)
