"""Environment-backed application settings with conservative defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    allow_local_execution: bool
    allow_local_sources: bool
    timeout_seconds: int
    max_output_bytes: int
    work_root: Path

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            allow_local_execution=_env_bool("FIXTRACE_ALLOW_LOCAL_EXECUTION"),
            allow_local_sources=_env_bool("FIXTRACE_ALLOW_LOCAL_SOURCES"),
            timeout_seconds=max(5, int(os.getenv("FIXTRACE_ANALYSIS_TIMEOUT_SECONDS", "120"))),
            max_output_bytes=max(10_000, int(os.getenv("FIXTRACE_MAX_OUTPUT_BYTES", "200000"))),
            work_root=Path(os.getenv("FIXTRACE_WORK_ROOT", ".fixtrace/workspaces")),
        )
