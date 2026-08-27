"""Typed domain models shared by the CLI, API, and analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExecutionMode(StrEnum):
    INSPECT = "inspect"
    LOCAL = "local"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StageName(StrEnum):
    INTAKE = "intake"
    CHECKOUT = "checkout"
    DETECT = "detect"
    REPRODUCE = "reproduce"
    DIAGNOSE = "diagnose"
    VERIFY = "verify"
    REPORT = "report"


class StageEvent(BaseModel):
    stage: StageName
    status: Literal["started", "completed", "skipped", "failed"]
    message: str
    occurred_at: datetime = Field(default_factory=utc_now)


class AnalysisRequest(BaseModel):
    repository: str = Field(
        min_length=1,
        max_length=500,
        description="Local directory or public https://github.com/owner/repository URL.",
    )
    failure_output: str = Field(
        default="",
        max_length=200_000,
        description="Optional pasted pytest/CI failure output for inspect-only analysis.",
    )
    execution_mode: ExecutionMode = ExecutionMode.INSPECT


class StackProfile(BaseModel):
    primary_language: str = "unknown"
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    manifests: list[str] = Field(default_factory=list)
    test_command: list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CommandResult(BaseModel):
    command: list[str]
    exit_code: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    truncated: bool = False

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


class Failure(BaseModel):
    test_id: str
    summary: str
    file: str | None = None
    line: int | None = None
    exception_type: str | None = None


class Evidence(BaseModel):
    id: str
    kind: Literal["stack", "test_failure", "source_location", "runtime", "constraint"]
    title: str
    detail: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)


class Hypothesis(BaseModel):
    id: str
    title: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    next_action: str


class AnalysisReport(BaseModel):
    repository: str
    source_kind: Literal["local", "github"]
    stack: StackProfile
    execution_mode: ExecutionMode
    command_result: CommandResult | None = None
    failures: list[Failure] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    verdict: str
    markdown: str
    created_at: datetime = Field(default_factory=utc_now)


class AnalysisTask(BaseModel):
    id: str
    request: AnalysisRequest
    status: TaskStatus = TaskStatus.QUEUED
    stages: list[StageEvent] = Field(default_factory=list)
    report: AnalysisReport | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
