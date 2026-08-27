"""Render a concise, portable Markdown evidence report."""

from __future__ import annotations

from typing import Literal

from fixtrace.core.models import (
    AnalysisReport,
    CommandResult,
    Evidence,
    ExecutionMode,
    Failure,
    Hypothesis,
    StackProfile,
    VerificationResult,
    VerificationStatus,
)


class ReportRenderer:
    def render(
        self,
        *,
        repository: str,
        source_kind: Literal["local", "github", "log"],
        stack: StackProfile,
        execution_mode: ExecutionMode,
        log_format: str,
        redaction_count: int,
        command_result: CommandResult | None,
        failures: list[Failure],
        evidence: list[Evidence],
        hypotheses: list[Hypothesis],
        verification: VerificationResult,
    ) -> AnalysisReport:
        verdict = self._verdict(execution_mode, command_result, failures, verification)
        lines = [
            "# FixTrace failure intelligence report",
            "",
            f"- Repository: `{repository}`",
            f"- Source: `{source_kind}`",
            f"- Primary language: `{stack.primary_language}`",
            f"- Frameworks: `{', '.join(stack.frameworks) or 'not detected'}`",
            f"- Log format: `{log_format}`",
            f"- Secrets redacted: `{redaction_count}`",
            f"- Execution mode: `{execution_mode.value}`",
            f"- Verdict: **{verdict}**",
            "",
            "## Reproduction",
            "",
        ]
        if command_result:
            lines.extend(
                [
                    f"Command: `{' '.join(command_result.command)}`",
                    "",
                    f"Exit code: `{command_result.exit_code}` in "
                    f"`{command_result.duration_seconds:.3f}s`.",
                ]
            )
        else:
            lines.append("No repository code was executed; supplied failure output was inspected.")

        lines.extend(["", "## Failures", ""])
        if failures:
            for failure in failures:
                location = failure.file or "unknown location"
                if failure.line:
                    location += f":{failure.line}"
                lines.append(
                    f"- `{failure.test_id}` — {failure.summary} ({location}); "
                    f"fingerprint: `{failure.fingerprint}`"
                )
        else:
            lines.append("No structured failure was identified.")

        lines.extend(["", "## Root-cause hypotheses", ""])
        if hypotheses:
            for hypothesis in hypotheses:
                lines.extend(
                    [
                        f"### {hypothesis.title} ({hypothesis.confidence:.0%})",
                        "",
                        hypothesis.explanation,
                        "",
                        f"Next action: {hypothesis.next_action}",
                        "",
                        f"Evidence: `{', '.join(hypothesis.evidence_ids)}`",
                        "",
                    ]
                )
        else:
            lines.append("Insufficient failure evidence for a root-cause hypothesis.")

        lines.extend(["", "## Evidence ledger", ""])
        for item in evidence:
            lines.append(
                f"- `{item.id}` **{item.title}** — {item.detail} "
                f"(source: {item.source}, confidence: {item.confidence:.0%})"
            )

        lines.extend(
            [
                "",
                "## Repair verification",
                "",
                f"Status: **{verification.status.value}**",
                "",
                verification.summary,
                "",
            ]
        )
        if verification.resolved_fingerprints:
            lines.append(
                "Resolved fingerprints: "
                + ", ".join(f"`{item}`" for item in verification.resolved_fingerprints)
            )
        if verification.remaining_fingerprints:
            lines.append(
                "Remaining fingerprints: "
                + ", ".join(f"`{item}`" for item in verification.remaining_fingerprints)
            )
        if verification.new_fingerprints:
            lines.append(
                "New fingerprints: "
                + ", ".join(f"`{item}`" for item in verification.new_fingerprints)
            )
        lines.append("")
        markdown = "\n".join(lines)
        return AnalysisReport(
            repository=repository,
            source_kind=source_kind,
            stack=stack,
            execution_mode=execution_mode,
            log_format=log_format,
            redaction_count=redaction_count,
            command_result=command_result,
            failures=failures,
            evidence=evidence,
            hypotheses=hypotheses,
            verification=verification,
            verdict=verdict,
            markdown=markdown,
        )

    @staticmethod
    def _verdict(
        execution_mode: ExecutionMode,
        command_result: CommandResult | None,
        failures: list[Failure],
        verification: VerificationResult,
    ) -> str:
        if verification.status == VerificationStatus.VERIFIED:
            return "repair verified"
        if verification.status == VerificationStatus.FAILED:
            return "repair not verified"
        if verification.status == VerificationStatus.INCONCLUSIVE:
            return "verification inconclusive"
        if command_result and command_result.timed_out:
            return "reproduction timed out"
        if command_result and command_result.exit_code == 0:
            return "failure not reproduced"
        if command_result and command_result.exit_code != 0 and failures:
            return "failure reproduced"
        if execution_mode == ExecutionMode.INSPECT and failures:
            return "failure evidence parsed"
        return "insufficient failure evidence"
