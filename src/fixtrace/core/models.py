"""Typed domain models shared by the CLI, API, and analysis pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExecutionMode(StrEnum):
    INSPECT = "inspect"
    LOCAL = "local"


class AgentMode(StrEnum):
    AUTO = "auto"
    OFF = "off"
    REQUIRED = "required"


class AgentStatus(StrEnum):
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS = "max_steps"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class IncidentDomain(StrEnum):
    TEST = "test"
    BUILD = "build"
    DEPENDENCY = "dependency"
    API = "api/network"
    DATABASE = "database"
    CONTAINER = "container/platform"
    CONFIGURATION = "configuration"
    RUNTIME = "application/runtime"
    UNKNOWN = "unknown"


class IncidentSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StageName(StrEnum):
    INTAKE = "intake"
    CHECKOUT = "checkout"
    DETECT = "detect"
    REPRODUCE = "reproduce"
    DIAGNOSE = "diagnose"
    INVESTIGATE = "investigate"
    VERIFY = "verify"
    REPORT = "report"


class StageEvent(BaseModel):
    stage: StageName
    status: Literal["started", "completed", "skipped", "failed"]
    message: str
    occurred_at: datetime = Field(default_factory=utc_now)


class AnalysisRequest(BaseModel):
    repository: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Optional local directory or public GitHub repository URL.",
    )
    failure_output: str = Field(
        default="",
        max_length=200_000,
        description="Failure output from a test, build, deployment, or application run.",
    )
    verification_output: str = Field(
        default="",
        max_length=200_000,
        description="Optional after-fix output used to prove whether the failure was resolved.",
    )
    execution_mode: ExecutionMode = ExecutionMode.INSPECT
    agent_mode: AgentMode = AgentMode.AUTO

    @model_validator(mode="after")
    def require_repository_or_failure(self) -> Self:
        if not self.repository and not self.failure_output.strip():
            raise ValueError("Provide a repository, failure output, or both.")
        if self.execution_mode == ExecutionMode.LOCAL and not self.repository:
            raise ValueError("Local execution requires a repository.")
        return self


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
    framework: str = "generic"
    fingerprint: str = ""


class Evidence(BaseModel):
    id: str
    kind: Literal[
        "stack",
        "test_failure",
        "source_location",
        "runtime",
        "constraint",
        "log_format",
        "privacy",
        "verification",
        "incident_signal",
    ]
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


class VerificationResult(BaseModel):
    status: VerificationStatus = VerificationStatus.PENDING
    summary: str = "No after-fix output was supplied."
    pass_signal: bool = False
    before_fingerprints: list[str] = Field(default_factory=list)
    after_fingerprints: list[str] = Field(default_factory=list)
    resolved_fingerprints: list[str] = Field(default_factory=list)
    remaining_fingerprints: list[str] = Field(default_factory=list)
    new_fingerprints: list[str] = Field(default_factory=list)


class IncidentSignal(BaseModel):
    kind: str
    label: str
    detail: str


class IncidentProfile(BaseModel):
    domain: IncidentDomain = IncidentDomain.UNKNOWN
    severity: IncidentSeverity = IncidentSeverity.WARNING
    title: str = "Unclassified software event"
    signals: list[IncidentSignal] = Field(default_factory=list)
    playbook: list[str] = Field(default_factory=list)


class AgentStep(BaseModel):
    index: int = Field(ge=1)
    action: str
    reason: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    observation_id: str | None = None


class AgentObservation(BaseModel):
    id: str
    tool: str
    ok: bool = True
    summary: str
    detail: str = ""


class AgentFinding(BaseModel):
    title: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class AgentInvestigation(BaseModel):
    status: AgentStatus
    provider: str = "none"
    model: str = "none"
    summary: str = ""
    steps: list[AgentStep] = Field(default_factory=list)
    observations: list[AgentObservation] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    model_calls: int = Field(default=0, ge=0)
    error: str | None = None


class AnalysisReport(BaseModel):
    repository: str
    source_kind: Literal["local", "github", "log"]
    stack: StackProfile
    execution_mode: ExecutionMode
    log_format: str = "generic"
    redaction_count: int = 0
    command_result: CommandResult | None = None
    failures: list[Failure] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    incident: IncidentProfile = Field(default_factory=IncidentProfile)
    agent: AgentInvestigation
    verification: VerificationResult = Field(default_factory=VerificationResult)
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
