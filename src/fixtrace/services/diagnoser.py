"""Deterministic evidence and root-cause hypothesis generation."""

from __future__ import annotations

from fixtrace.core.models import (
    CommandResult,
    Evidence,
    Failure,
    Hypothesis,
    StackProfile,
    VerificationResult,
)


class EvidenceDiagnoser:
    @staticmethod
    def verification_evidence(verification: VerificationResult) -> Evidence:
        return Evidence(
            id="ev-verification",
            kind="verification",
            title=f"Repair verification: {verification.status.value}",
            detail=verification.summary,
            source="before/after failure fingerprint comparison",
            confidence=1.0 if verification.status.value in {"verified", "failed"} else 0.65,
        )

    def build_evidence(
        self,
        stack: StackProfile,
        failures: list[Failure],
        command_result: CommandResult | None,
        *,
        log_format: str,
        redaction_count: int,
    ) -> list[Evidence]:
        evidence = [
            Evidence(
                id="ev-format",
                kind="log_format",
                title=f"Detected {log_format} output",
                detail="The parser was selected from deterministic log signatures.",
                source="supplied or reproduced output",
                confidence=0.95 if log_format != "generic" else 0.5,
            )
        ]
        if stack.primary_language != "unknown":
            evidence.append(
                Evidence(
                    id="ev-stack",
                    kind="stack",
                    title=f"Detected {stack.primary_language} project",
                    detail=self._stack_detail(stack),
                    source="repository manifests and file extensions",
                    confidence=stack.confidence,
                )
            )
        if redaction_count:
            evidence.append(
                Evidence(
                    id="ev-privacy",
                    kind="privacy",
                    title=f"Redacted {redaction_count} potential secret(s)",
                    detail="Sensitive values were replaced before parsing and reporting.",
                    source="local privacy filter",
                    confidence=1.0,
                )
            )
        if command_result:
            evidence.append(
                Evidence(
                    id="ev-runtime",
                    kind="runtime",
                    title=f"Test command exited with code {command_result.exit_code}",
                    detail=(
                        f"Duration {command_result.duration_seconds:.3f}s; "
                        f"timed_out={command_result.timed_out}; "
                        f"truncated={command_result.truncated}."
                    ),
                    source="isolated repository copy",
                    confidence=1.0,
                )
            )
        for index, failure in enumerate(failures, start=1):
            evidence.append(
                Evidence(
                    id=f"ev-failure-{index}",
                    kind="test_failure",
                    title=failure.test_id,
                    detail=f"{failure.summary} Fingerprint: {failure.fingerprint}.",
                    source=f"{failure.framework} output",
                    confidence=0.95,
                )
            )
            if failure.file:
                suffix = f":{failure.line}" if failure.line else ""
                evidence.append(
                    Evidence(
                        id=f"ev-location-{index}",
                        kind="source_location",
                        title=f"Failure location: {failure.file}{suffix}",
                        detail=(
                            "The location is linked from the failing test identifier or traceback."
                        ),
                        source=f"{failure.framework} traceback or source location",
                        confidence=0.85 if failure.line else 0.7,
                    )
                )
        if not failures:
            evidence.append(
                Evidence(
                    id="ev-no-failure",
                    kind="constraint",
                    title="No structured failure was found",
                    detail="Provide pytest output or opt in to trusted local execution.",
                    source="analysis request",
                    confidence=1.0,
                )
            )
        return evidence

    def build_hypotheses(
        self,
        failures: list[Failure],
        command_result: CommandResult | None,
    ) -> list[Hypothesis]:
        if command_result and command_result.timed_out:
            return [
                Hypothesis(
                    id="hyp-timeout",
                    title="Test suite is blocked or exceeds the time budget",
                    explanation="The reproduction command reached the configured timeout.",
                    confidence=0.9,
                    evidence_ids=["ev-runtime"],
                    next_action=(
                        "Run the slowest test in isolation and inspect blocking I/O or deadlocks."
                    ),
                )
            ]
        if not failures:
            return []

        hypotheses: list[Hypothesis] = []
        seen: set[str] = set()
        for index, failure in enumerate(failures, start=1):
            category, title, explanation, action, confidence = self._classify(failure)
            if category in seen:
                continue
            seen.add(category)
            ids = [f"ev-failure-{index}"]
            if failure.file:
                ids.append(f"ev-location-{index}")
            hypotheses.append(
                Hypothesis(
                    id=f"hyp-{category}",
                    title=title,
                    explanation=explanation,
                    confidence=confidence,
                    evidence_ids=ids,
                    next_action=action,
                )
            )
        return sorted(hypotheses, key=lambda item: item.confidence, reverse=True)

    @staticmethod
    def _stack_detail(stack: StackProfile) -> str:
        frameworks = ", ".join(stack.frameworks) or "none detected"
        manifests = ", ".join(stack.manifests) or "none detected"
        return f"Frameworks: {frameworks}. Manifests: {manifests}."

    @staticmethod
    def _classify(failure: Failure) -> tuple[str, str, str, str, float]:
        failure_type = failure.exception_type or ""
        summary = failure.summary.lower()
        if failure_type in {"ModuleNotFoundError", "ImportError"}:
            return (
                "dependency",
                "Dependency or import environment mismatch",
                "The failure occurs before the tested behavior runs and points to "
                "an unavailable import.",
                "Compare declared dependencies with the CI environment and reproduce "
                "in a clean environment.",
                0.91,
            )
        if failure_type == "SyntaxError":
            return (
                "syntax",
                "Syntax or interpreter-version incompatibility",
                "Python could not parse a source or test module.",
                "Inspect the reported line and verify the project's supported Python versions.",
                0.96,
            )
        if failure_type == "BuildError":
            return (
                "build",
                "Build or compiler contract failed",
                "A compiler or build tool rejected a source location before runtime.",
                "Inspect the normalized source location and reproduce with the same toolchain.",
                0.88,
            )
        if failure_type == "AssertionError" or "assert" in summary:
            return (
                "behavior",
                "Behavioral regression against an asserted contract",
                "The code executed, but its result differs from the test's expected behavior.",
                "Trace inputs and outputs around the failing assertion, then add a "
                "minimal regression test.",
                0.82,
            )
        if failure_type in {"TypeError", "AttributeError", "KeyError", "ValueError"}:
            return (
                "data-contract",
                "Runtime data-contract mismatch",
                "The observed exception usually indicates an unexpected value, type, "
                "key, or object shape.",
                "Inspect the first project-owned traceback frame and validate data at "
                "the boundary.",
                0.78,
            )
        return (
            "runtime",
            "Unhandled runtime failure",
            "Pytest reported a failure that needs source-level tracing before a "
            "specific cause is proven.",
            "Re-run the failing test with verbose traceback and inspect the first "
            "project-owned frame.",
            0.58,
        )
