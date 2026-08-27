"""Seven-stage, evidence-first analysis pipeline."""

from __future__ import annotations

from collections.abc import Callable

from fixtrace.agent.provider import AgentModel, build_agent_model
from fixtrace.agent.runtime import AgentRunner
from fixtrace.core.config import Settings
from fixtrace.core.models import (
    AgentInvestigation,
    AgentMode,
    AgentStatus,
    AnalysisReport,
    AnalysisRequest,
    ExecutionMode,
    StageEvent,
    StageName,
)
from fixtrace.services.diagnoser import EvidenceDiagnoser
from fixtrace.services.failure_parser import UniversalFailureParser
from fixtrace.services.incident_classifier import IncidentClassifier
from fixtrace.services.redactor import SecretRedactor
from fixtrace.services.report import ReportRenderer
from fixtrace.services.repository import RepositoryManager
from fixtrace.services.stack_detector import StackDetector
from fixtrace.services.test_runner import LocalTestRunner
from fixtrace.services.verifier import RepairVerifier

StageCallback = Callable[[StageEvent], None]


class AnalysisPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        allow_local_execution: bool | None = None,
        allow_local_sources: bool | None = None,
        agent_model: AgentModel | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        execution_enabled = (
            self.settings.allow_local_execution
            if allow_local_execution is None
            else allow_local_execution
        )
        local_sources_enabled = (
            self.settings.allow_local_sources
            if allow_local_sources is None
            else allow_local_sources
        )
        self.repositories = RepositoryManager(
            self.settings.work_root,
            allow_local_sources=local_sources_enabled,
        )
        self.detector = StackDetector()
        self.runner = LocalTestRunner(
            enabled=execution_enabled,
            timeout_seconds=self.settings.timeout_seconds,
            max_output_bytes=self.settings.max_output_bytes,
        )
        self.parser = UniversalFailureParser()
        self.redactor = SecretRedactor()
        self.verifier = RepairVerifier(self.parser)
        self.incidents = IncidentClassifier()
        self.diagnoser = EvidenceDiagnoser()
        self.renderer = ReportRenderer()
        self.agent = AgentRunner(
            agent_model or build_agent_model(self.settings),
            max_steps=self.settings.agent_max_steps,
            max_tool_output_chars=self.settings.agent_max_tool_output_chars,
            redactor=self.redactor,
        )

    def run(
        self,
        request: AnalysisRequest,
        on_stage: StageCallback | None = None,
    ) -> AnalysisReport:
        emit = on_stage or (lambda _event: None)
        self._stage(emit, StageName.INTAKE, "started", "Validated analysis request.")
        self._stage(emit, StageName.INTAKE, "completed", "Analysis inputs are ready.")

        isolated = request.execution_mode == ExecutionMode.LOCAL
        self._stage(emit, StageName.CHECKOUT, "started", "Preparing repository source.")
        with self.repositories.prepare(request.repository, isolated=isolated) as checkout:
            self._stage(
                emit,
                StageName.CHECKOUT,
                "completed",
                f"Prepared {checkout.source_kind} repository {checkout.display_name}.",
            )

            self._stage(emit, StageName.DETECT, "started", "Detecting stack and test runner.")
            stack = self.detector.detect(checkout.path)
            self._stage(
                emit,
                StageName.DETECT,
                "completed",
                f"Detected {stack.primary_language}; frameworks: "
                f"{', '.join(stack.frameworks) or 'none'}.",
            )

            command_result = None
            redaction_count = 0
            if request.execution_mode == ExecutionMode.LOCAL:
                self._stage(emit, StageName.REPRODUCE, "started", "Running trusted local pytest.")
                command_result = self.runner.run(checkout.path, stack.test_command)
                clean_stdout = self.redactor.redact(command_result.stdout)
                clean_stderr = self.redactor.redact(command_result.stderr)
                redaction_count += clean_stdout.count + clean_stderr.count
                command_result = command_result.model_copy(
                    update={"stdout": clean_stdout.text, "stderr": clean_stderr.text}
                )
                output = command_result.combined_output
                self._stage(
                    emit,
                    StageName.REPRODUCE,
                    "completed",
                    f"Test process exited with code {command_result.exit_code}.",
                )
            else:
                clean_failure = self.redactor.redact(request.failure_output)
                output = clean_failure.text
                redaction_count += clean_failure.count
                message = (
                    "Parsed supplied failure output without executing repository code."
                    if output.strip()
                    else "No failure output supplied; repository inspection only."
                )
                self._stage(emit, StageName.REPRODUCE, "skipped", message)

            self._stage(emit, StageName.DIAGNOSE, "started", "Building evidence ledger.")
            log_format = self.parser.detect_format(output)
            failures = self.parser.parse(output)
            clean_verification = self.redactor.redact(request.verification_output)
            redaction_count += clean_verification.count
            evidence = self.diagnoser.build_evidence(
                stack,
                failures,
                command_result,
                log_format=log_format,
                redaction_count=redaction_count,
            )
            incident = self.incidents.classify(output, log_format, failures)
            evidence.append(self.diagnoser.incident_evidence(incident))
            hypotheses = self.diagnoser.build_hypotheses(failures, command_result)
            self._stage(
                emit,
                StageName.DIAGNOSE,
                "completed",
                f"Collected {len(evidence)} evidence items and {len(hypotheses)} hypotheses.",
            )

            verification = self.verifier.verify(failures, clean_verification.text)
            if request.verification_output.strip():
                evidence.append(self.diagnoser.verification_evidence(verification))
            self._stage(
                emit,
                StageName.INVESTIGATE,
                "started",
                "Starting bounded LLM investigation with read-only tools.",
            )
            if request.agent_mode == AgentMode.OFF:
                agent = AgentInvestigation(
                    status=AgentStatus.DISABLED,
                    summary="LLM investigation was disabled for this request.",
                )
            else:
                agent = self.agent.run(
                    repository_root=checkout.path,
                    repository=checkout.display_name,
                    stack=stack,
                    incident=incident,
                    failures=failures,
                    evidence=evidence,
                    failure_output=output,
                    verification=verification,
                )
            if agent.status == AgentStatus.COMPLETED:
                self._stage(
                    emit,
                    StageName.INVESTIGATE,
                    "completed",
                    f"Agent completed {agent.model_calls} model calls and produced "
                    f"{len(agent.findings)} evidence-cited findings.",
                )
            elif agent.status in {AgentStatus.DISABLED, AgentStatus.NOT_CONFIGURED}:
                self._stage(emit, StageName.INVESTIGATE, "skipped", agent.summary)
            else:
                self._stage(emit, StageName.INVESTIGATE, "failed", agent.summary)
            if request.agent_mode == AgentMode.REQUIRED and agent.status != AgentStatus.COMPLETED:
                raise RuntimeError(
                    "Agent investigation was required but did not complete: "
                    f"{agent.status.value}."
                )

            if request.verification_output.strip():
                self._stage(
                    emit,
                    StageName.VERIFY,
                    "completed",
                    f"Repair verification is {verification.status.value}.",
                )
            else:
                self._stage(
                    emit,
                    StageName.VERIFY,
                    "skipped",
                    "No after-fix output was supplied; repair verification is pending.",
                )
            self._stage(emit, StageName.REPORT, "started", "Rendering portable Markdown report.")
            report = self.renderer.render(
                repository=checkout.display_name,
                source_kind=checkout.source_kind,
                stack=stack,
                execution_mode=request.execution_mode,
                log_format=log_format,
                redaction_count=redaction_count,
                command_result=command_result,
                failures=failures,
                evidence=evidence,
                hypotheses=hypotheses,
                incident=incident,
                agent=agent,
                verification=verification,
            )
            self._stage(emit, StageName.REPORT, "completed", "Analysis report is ready.")
            return report

    @staticmethod
    def _stage(
        callback: StageCallback,
        stage: StageName,
        status: str,
        message: str,
    ) -> None:
        callback(StageEvent(stage=stage, status=status, message=message))  # type: ignore[arg-type]
