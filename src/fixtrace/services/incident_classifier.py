"""Classify software incidents and build a deterministic first-response playbook."""

from __future__ import annotations

import re

from fixtrace.core.models import (
    Failure,
    IncidentDomain,
    IncidentProfile,
    IncidentSeverity,
    IncidentSignal,
)

_HTTP_STATUS = re.compile(
    r"(?:HTTP/\d(?:\.\d)?\s+|status(?:[_ ]code)?\s*[:=]\s*|response\s+)"
    r"(?P<status>[1-5]\d\d)\b",
    re.I,
)
_ERROR_CODE = re.compile(
    r"\b(?:SQLSTATE(?:\[[A-Z0-9]+\]|\s+[A-Z0-9]+)|ERR_[A-Z0-9_]+|"
    r"TS\d{3,5}|OOMKilled|CrashLoopBackOff|ImagePullBackOff)\b"
)
_TIMESTAMP = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d:[0-5]\d(?:\.\d+)?Z?\b")
_TRACE_ID = re.compile(
    r"\b(?:trace|request|correlation)[_-]?id\s*[:=]\s*(?:[A-Za-z0-9._-]+|\[REDACTED\])",
    re.I,
)

_TITLES = {
    IncidentDomain.TEST: "Automated test contract failed",
    IncidentDomain.BUILD: "Build or compilation failed",
    IncidentDomain.DEPENDENCY: "Dependency resolution or import failed",
    IncidentDomain.API: "API or network request failed",
    IncidentDomain.DATABASE: "Database operation failed",
    IncidentDomain.CONTAINER: "Container or platform workload failed",
    IncidentDomain.CONFIGURATION: "Runtime configuration is incomplete",
    IncidentDomain.RUNTIME: "Application runtime failed",
    IncidentDomain.UNKNOWN: "Software event needs more structured evidence",
}

_PLAYBOOKS = {
    IncidentDomain.TEST: [
        "Run the smallest failing test with the same inputs and environment.",
        "Inspect the first project-owned frame and the asserted contract.",
        "Keep the failing test as a regression check after the repair.",
    ],
    IncidentDomain.BUILD: [
        "Re-run the exact build command with the same toolchain version.",
        "Open the first normalized source location, not the final summary line.",
        "Compare compiler, lockfile, and generated-artifact versions with the last good run.",
    ],
    IncidentDomain.DEPENDENCY: [
        "Reproduce installation in a clean environment using the committed lockfile.",
        "Compare requested and resolved package versions across environments.",
        "Verify registry access and supported interpreter or runtime versions.",
    ],
    IncidentDomain.API: [
        "Confirm the failing method, route, status code, and timeout boundary.",
        "Check upstream health and trace the same request with a correlation identifier.",
        "Retry only if the operation is safe and the failure is transient.",
    ],
    IncidentDomain.DATABASE: [
        "Capture the database error code and the operation that triggered it.",
        "Check connection-pool, lock, storage, and migration state.",
        "Reproduce with sanitized parameters against a non-production database.",
    ],
    IncidentDomain.CONTAINER: [
        "Inspect workload events, previous container logs, and termination reason.",
        "Compare resource requests, limits, image digest, and configuration with the "
        "last good run.",
        "Verify readiness and liveness probes before restarting repeatedly.",
    ],
    IncidentDomain.CONFIGURATION: [
        "List required configuration keys without printing their secret values.",
        "Compare configuration names and deployment scope with the last good environment.",
        "Fail fast at startup with a clear message for missing values.",
    ],
    IncidentDomain.RUNTIME: [
        "Locate the first application-owned stack frame and preserve the triggering input shape.",
        "Check recent code, configuration, and dependency changes around that path.",
        "Add a minimal regression case before applying the repair.",
    ],
    IncidentDomain.UNKNOWN: [
        "Include the first error line, surrounding context, and the command or action that failed.",
        "Add timestamps and component names while removing credentials and personal data.",
        "Provide a known-good rerun so FixTrace can compare before and after evidence.",
    ],
}


class IncidentClassifier:
    def classify(self, output: str, log_format: str, failures: list[Failure]) -> IncidentProfile:
        domain = self._domain(output, log_format)
        severity = self._severity(output, failures)
        signals = self._signals(output, failures)
        return IncidentProfile(
            domain=domain,
            severity=severity,
            title=_TITLES[domain],
            signals=signals,
            playbook=_PLAYBOOKS[domain],
        )

    @staticmethod
    def _domain(output: str, log_format: str) -> IncidentDomain:
        normalized = output.lower()
        if log_format in {"pytest", "jest/vitest", "go test"}:
            return IncidentDomain.TEST
        if log_format == "maven/gradle":
            return (
                IncidentDomain.TEST
                if "Tests run:" in output or "<<< FAILURE!" in output
                else IncidentDomain.BUILD
            )
        if log_format == "compiler":
            return IncidentDomain.BUILD
        if log_format == "dependency":
            return IncidentDomain.DEPENDENCY
        if log_format == "http/api":
            return IncidentDomain.API
        if log_format == "database":
            return IncidentDomain.DATABASE
        if log_format == "container/platform":
            return IncidentDomain.CONTAINER
        if re.search(r"missing|required|not set|undefined", normalized) and re.search(
            r"env|environment|config|setting", normalized
        ):
            return IncidentDomain.CONFIGURATION
        if log_format in {"runtime", "application"}:
            return IncidentDomain.RUNTIME
        return IncidentDomain.UNKNOWN

    @staticmethod
    def _severity(output: str, failures: list[Failure]) -> IncidentSeverity:
        if re.search(
            r"\b(?:OOMKilled|CrashLoopBackOff|PANIC|FATAL|corrupt(?:ion|ed)?|data loss)\b",
            output,
            re.I,
        ):
            return IncidentSeverity.CRITICAL
        if failures:
            return IncidentSeverity.ERROR
        return IncidentSeverity.WARNING

    @staticmethod
    def _signals(output: str, failures: list[Failure]) -> list[IncidentSignal]:
        signals: list[IncidentSignal] = []
        if failures:
            signals.append(
                IncidentSignal(
                    kind="failure_count",
                    label="Normalized failures",
                    detail=f"{len(failures)} unique failure record(s) were extracted.",
                )
            )
        statuses = sorted({match.group("status") for match in _HTTP_STATUS.finditer(output)})
        if statuses:
            signals.append(
                IncidentSignal(
                    kind="http_status",
                    label="HTTP status",
                    detail=", ".join(statuses[:5]),
                )
            )
        codes = list(dict.fromkeys(match.group(0) for match in _ERROR_CODE.finditer(output)))
        if codes:
            signals.append(
                IncidentSignal(
                    kind="error_code",
                    label="Error code or platform reason",
                    detail=", ".join(codes[:5]),
                )
            )
        locations = sorted(
            {
                f"{failure.file}:{failure.line}" if failure.line else failure.file
                for failure in failures
                if failure.file
            }
        )
        if locations:
            signals.append(
                IncidentSignal(
                    kind="source_location",
                    label="Source location",
                    detail=", ".join(locations[:5]),
                )
            )
        timestamp = _TIMESTAMP.search(output)
        if timestamp:
            signals.append(
                IncidentSignal(
                    kind="timestamp",
                    label="Timestamp present",
                    detail=timestamp.group(0),
                )
            )
        if _TRACE_ID.search(output):
            signals.append(
                IncidentSignal(
                    kind="trace_context",
                    label="Trace context present",
                    detail="A request, trace, or correlation identifier can link related logs.",
                )
            )
        if re.search(r"\b(?:timeout|timed out|deadline exceeded)\b", output, re.I):
            signals.append(
                IncidentSignal(
                    kind="timeout",
                    label="Timeout signal",
                    detail="The failure crossed a configured time boundary.",
                )
            )
        return signals[:8]
