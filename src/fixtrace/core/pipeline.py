"""Seven-stage, evidence-first analysis pipeline."""

from __future__ import annotations

from collections.abc import Callable

from fixtrace.core.config import Settings
from fixtrace.core.models import (
    AnalysisReport,
    AnalysisRequest,
    ExecutionMode,
    StageEvent,
    StageName,
)
from fixtrace.services.diagnoser import EvidenceDiagnoser
from fixtrace.services.failure_parser import PytestFailureParser
from fixtrace.services.report import ReportRenderer
from fixtrace.services.repository import RepositoryManager
from fixtrace.services.stack_detector import StackDetector
from fixtrace.services.test_runner import LocalTestRunner

StageCallback = Callable[[StageEvent], None]


class AnalysisPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        allow_local_execution: bool | None = None,
        allow_local_sources: bool | None = None,
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
        self.parser = PytestFailureParser()
        self.diagnoser = EvidenceDiagnoser()
        self.renderer = ReportRenderer()

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
            if request.execution_mode == ExecutionMode.LOCAL:
                self._stage(emit, StageName.REPRODUCE, "started", "Running trusted local pytest.")
                command_result = self.runner.run(checkout.path, stack.test_command)
                output = command_result.combined_output
                self._stage(
                    emit,
                    StageName.REPRODUCE,
                    "completed",
                    f"Test process exited with code {command_result.exit_code}.",
                )
            else:
                output = request.failure_output
                message = (
                    "Parsed supplied CI output without executing repository code."
                    if output.strip()
                    else "No CI output supplied; repository inspection only."
                )
                self._stage(emit, StageName.REPRODUCE, "skipped", message)

            self._stage(emit, StageName.DIAGNOSE, "started", "Building evidence ledger.")
            failures = self.parser.parse(output)
            evidence = self.diagnoser.build_evidence(stack, failures, command_result)
            hypotheses = self.diagnoser.build_hypotheses(failures, command_result)
            self._stage(
                emit,
                StageName.DIAGNOSE,
                "completed",
                f"Collected {len(evidence)} evidence items and {len(hypotheses)} hypotheses.",
            )

            self._stage(
                emit,
                StageName.VERIFY,
                "skipped",
                "No candidate patch was supplied; baseline verification is pending.",
            )
            self._stage(emit, StageName.REPORT, "started", "Rendering portable Markdown report.")
            report = self.renderer.render(
                repository=checkout.display_name,
                source_kind=checkout.source_kind,
                stack=stack,
                execution_mode=request.execution_mode,
                command_result=command_result,
                failures=failures,
                evidence=evidence,
                hypotheses=hypotheses,
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
