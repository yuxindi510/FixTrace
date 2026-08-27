"""Environment-backed application settings with conservative defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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
    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = field(default=None, repr=False)
    llm_timeout_seconds: int = 60
    agent_max_steps: int = 6
    agent_max_tool_output_chars: int = 12_000

    @property
    def llm_configured(self) -> bool:
        return (
            self.llm_provider == "openai"
            and bool(self.llm_model.strip())
            and bool(self.llm_api_key)
        )

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("FIXTRACE_LLM_PROVIDER", "disabled").strip().lower()
        if provider not in {"disabled", "openai"}:
            raise ValueError("FIXTRACE_LLM_PROVIDER must be 'disabled' or 'openai'.")
        return cls(
            allow_local_execution=_env_bool("FIXTRACE_ALLOW_LOCAL_EXECUTION"),
            allow_local_sources=_env_bool("FIXTRACE_ALLOW_LOCAL_SOURCES"),
            timeout_seconds=max(5, int(os.getenv("FIXTRACE_ANALYSIS_TIMEOUT_SECONDS", "120"))),
            max_output_bytes=max(10_000, int(os.getenv("FIXTRACE_MAX_OUTPUT_BYTES", "200000"))),
            work_root=Path(os.getenv("FIXTRACE_WORK_ROOT", ".fixtrace/workspaces")),
            llm_provider=provider,
            llm_model=os.getenv("FIXTRACE_LLM_MODEL", "").strip(),
            llm_base_url=os.getenv(
                "FIXTRACE_LLM_BASE_URL", "https://api.openai.com/v1"
            ).strip(),
            llm_api_key=os.getenv("FIXTRACE_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            llm_timeout_seconds=max(
                5, min(300, int(os.getenv("FIXTRACE_LLM_TIMEOUT_SECONDS", "60")))
            ),
            agent_max_steps=max(
                1, min(12, int(os.getenv("FIXTRACE_AGENT_MAX_STEPS", "6")))
            ),
            agent_max_tool_output_chars=max(
                2_000,
                min(50_000, int(os.getenv("FIXTRACE_AGENT_MAX_TOOL_OUTPUT_CHARS", "12000"))),
            ),
        )
