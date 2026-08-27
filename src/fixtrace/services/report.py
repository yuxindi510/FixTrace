"""Render a concise, portable Markdown evidence report."""

from __future__ import annotations

from typing import Literal

from fixtrace.core.models import (
    AgentInvestigation,
    AnalysisReport,
    CommandResult,
    Evidence,
    ExecutionMode,
    Failure,
    Hypothesis,
    IncidentProfile,
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
        incident: IncidentProfile,
        agent: AgentInvestigation,
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
            f"- Sensitive values redacted: `{redaction_count}`",
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

        lines.extend(
            [
                "",
                "## Incident profile",
                "",
                f"- Domain: `{incident.domain.value}`",
                f"- Severity: `{incident.severity.value}`",
                f"- Classification: {incident.title}",
                "",
                "### Key signals",
                "",
            ]
        )
        if incident.signals:
            for signal in incident.signals:
                lines.append(f"- **{signal.label}** — {signal.detail}")
        else:
            lines.append("No structured operational signal was extracted.")
        lines.extend(["", "### First-response playbook", ""])
        for index, action in enumerate(incident.playbook, start=1):
            lines.append(f"{index}. {action}")

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

        lines.extend(
            [
                "",
                "## Agent investigation",
                "",
                f"Status: **{agent.status.value}**",
                "",
            ]
        )
        if agent.provider != "none":
            lines.append(f"Provider/model: `{agent.provider}` / `{agent.model}`")
            lines.append("")
        lines.append(
            self._agent_text(agent.summary) or "No LLM investigation summary is available."
        )
        if agent.findings:
            lines.extend(["", "### Evidence-cited findings", ""])
            for finding in agent.findings:
                citations = finding.evidence_ids + finding.observation_ids
                lines.extend(
                    [
                        f"#### {self._agent_text(finding.title)} ({finding.confidence:.0%})",
                        "",
                        self._agent_text(finding.explanation),
                        "",
                        f"Citations: `{', '.join(citations)}`",
                        "",
                    ]
                )
                for action in finding.next_actions:
                    lines.append(f"- {self._agent_text(action)}")
        if agent.steps:
            lines.extend(["", "### Agent trace", ""])
            for step in agent.steps:
                observation = f" → `{step.observation_id}`" if step.observation_id else ""
                lines.append(
                    f"- Step {step.index}: `{step.action}`{observation} — "
                    f"{self._agent_text(step.reason)}"
                )
        if agent.observations:
            lines.extend(["", "### Agent observation ledger", ""])
            for observation in agent.observations:
                outcome = "ok" if observation.ok else "rejected"
                lines.extend(
                    [
                        f"#### `{observation.id}` · `{observation.tool}` · {outcome}",
                        "",
                        self._agent_text(observation.summary),
                        "",
                    ]
                )
                lines.extend(
                    f"    {self._agent_text(line)}"
                    for line in observation.detail[:2_000].splitlines()
                )
                lines.append("")

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
            incident=incident,
            agent=agent,
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

    @staticmethod
    def _agent_text(value: str) -> str:
        return value.replace("\r", "").replace("<", "&lt;").replace(">", "&gt;")
