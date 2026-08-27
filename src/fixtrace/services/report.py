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
)


class ReportRenderer:
    def render(
        self,
        *,
        repository: str,
        source_kind: Literal["local", "github"],
        stack: StackProfile,
        execution_mode: ExecutionMode,
        command_result: CommandResult | None,
        failures: list[Failure],
        evidence: list[Evidence],
        hypotheses: list[Hypothesis],
    ) -> AnalysisReport:
        verdict = self._verdict(execution_mode, command_result, failures)
        lines = [
            "# FixTrace analysis report",
            "",
            f"- Repository: `{repository}`",
            f"- Source: `{source_kind}`",
            f"- Primary language: `{stack.primary_language}`",
            f"- Frameworks: `{', '.join(stack.frameworks) or 'not detected'}`",
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
            lines.append("No repository code was executed; supplied CI output was inspected.")

        lines.extend(["", "## Failures", ""])
        if failures:
            for failure in failures:
                location = failure.file or "unknown location"
                if failure.line:
                    location += f":{failure.line}"
                lines.append(f"- `{failure.test_id}` — {failure.summary} ({location})")
        else:
            lines.append("No structured pytest failure was identified.")

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
                "## Verification status",
                "",
                "This MVP records the baseline failure. A candidate patch must pass "
                "the failing test "
                "and the full regression suite before the report can mark the repair as verified.",
                "",
            ]
        )
        markdown = "\n".join(lines)
        return AnalysisReport(
            repository=repository,
            source_kind=source_kind,
            stack=stack,
            execution_mode=execution_mode,
            command_result=command_result,
            failures=failures,
            evidence=evidence,
            hypotheses=hypotheses,
            verdict=verdict,
            markdown=markdown,
        )

    @staticmethod
    def _verdict(
        execution_mode: ExecutionMode,
        command_result: CommandResult | None,
        failures: list[Failure],
    ) -> str:
        if command_result and command_result.timed_out:
            return "reproduction timed out"
        if command_result and command_result.exit_code == 0:
            return "failure not reproduced"
        if command_result and command_result.exit_code != 0 and failures:
            return "failure reproduced"
        if execution_mode == ExecutionMode.INSPECT and failures:
            return "failure evidence parsed"
        return "insufficient failure evidence"
