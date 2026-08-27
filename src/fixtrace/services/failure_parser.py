"""Normalize failures from common test, build, and runtime log formats."""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePath

from fixtrace.core.models import Failure

_PYTEST_FAILURE = re.compile(
    r"^(?:FAILED|ERROR)\s+(?P<test>\S+?)(?:\s+-\s+(?P<summary>.+))?$", re.M
)
_PYTHON_LOCATION = re.compile(r"^(?P<file>[^\n:]+\.py):(?P<line>\d+)(?::|\s)", re.M)
_EXCEPTION = re.compile(
    r"^(?:E\s+|Caused by:\s*)?(?P<type>[A-Za-z_][\w.]*(?:Error|Exception))"
    r"(?::\s*(?P<detail>.*))?$",
    re.M,
)
_JEST_FAILURE = re.compile(r"^\s*FAIL\s+(?P<file>\S+)", re.M)
_JEST_TEST = re.compile(r"^\s*[●✕×]\s+(?P<test>.+)$", re.M)
_JS_LOCATION = re.compile(
    r"(?:\(|\s)(?P<file>[^\s():]+\.(?:[cm]?[jt]sx?)):(?P<line>\d+):\d+\)?"
)
_GO_FAILURE = re.compile(r"^--- FAIL:\s+(?P<test>\S+)", re.M)
_GO_LOCATION = re.compile(
    r"^\s*(?P<file>[^\s:]+_test\.go):(?P<line>\d+):\s*(?P<detail>.+)$", re.M
)
_JAVA_FAILURE = re.compile(
    r"^\[ERROR\]\s+(?P<test>[\w.$]+(?:\.[\w$]+)?)\s+.*<<<\s+(?:FAILURE|ERROR)!",
    re.M,
)
_JAVA_LOCATION = re.compile(r"\((?P<file>[A-Za-z0-9_$]+\.java):(?P<line>\d+)\)")
_COMPILER_ERROR = re.compile(
    r"^(?P<file>[^\n:()]+\.[A-Za-z0-9]+)"
    r"(?:\((?P<paren_line>\d+),\d+\)|:(?P<line>\d+)(?::\d+)?)"
    r"\s*:?\s*(?:error(?:\s+[A-Z]+\d+)?:\s*)?(?P<detail>.+)$",
    re.I | re.M,
)
_HTTP_FAILURE = re.compile(
    r"(?:HTTP/\d(?:\.\d)?\s+|status(?:[_ ]code)?\s*[:=]\s*|response\s+)"
    r"(?P<status>[45]\d\d)\b(?P<detail>[^\n]*)",
    re.I,
)
_HTTP_REQUEST = re.compile(r"\b(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD)\s+(?P<path>/\S*)", re.I)
_NETWORK_FAILURE = re.compile(
    r"(?P<detail>ECONNREFUSED[^\n]*|ENOTFOUND[^\n]*|ConnectionRefusedError[^\n]*|"
    r"connection reset by peer[^\n]*|upstream timed out[^\n]*|DNS lookup failed[^\n]*)",
    re.I,
)
_CONTAINER_FAILURE = re.compile(
    r"(?P<reason>OOMKilled|CrashLoopBackOff|ImagePullBackOff|CreateContainerConfigError|"
    r"Evicted|Back-off restarting failed container)",
    re.I,
)
_DATABASE_FAILURE = re.compile(
    r"(?P<detail>SQLSTATE(?:\[[A-Z0-9]+\]|\s+[A-Z0-9]+)[^\n]*|deadlock detected[^\n]*|"
    r"too many connections[^\n]*|connection pool (?:exhausted|timeout)[^\n]*|"
    r"database is locked[^\n]*|could not connect to (?:database|server)[^\n]*)",
    re.I,
)
_DEPENDENCY_FAILURE = re.compile(
    r"(?P<detail>npm ERR![^\n]*|No matching distribution found[^\n]*|"
    r"Could not find a version that satisfies[^\n]*|ResolutionImpossible[^\n]*|"
    r"ModuleNotFoundError:[^\n]*|Cannot find module[^\n]*)",
    re.I,
)
_APPLICATION_FAILURE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}[T ][^\s]+\s+)?(?:\[[^\]]+\]\s*)?"
    r"(?:ERROR|FATAL|PANIC|CRITICAL)\b\s*[:\-]?\s*(?P<detail>.+)$",
    re.I | re.M,
)


def failure_fingerprint(failure: Failure) -> str:
    """Build a stable, non-reversible identifier for a normalized failure."""

    test_id = re.sub(r"\b\d+\b", "#", failure.test_id.lower())
    summary = failure.summary.lower()
    signature_codes = ",".join(
        match.group(0).lower()
        for match in re.finditer(
            r"\b(?:HTTP\s+[45]\d\d|SQLSTATE(?:\[[A-Z0-9]+\]|\s+[A-Z0-9]+)|"
            r"ERR_[A-Z0-9_]+|TS\d{3,5}|OOMKilled|CrashLoopBackOff|ImagePullBackOff)\b",
            failure.summary,
            re.I,
        )
    )
    summary = re.sub(r"0x[0-9a-f]+", "<hex>", summary)
    summary = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", summary)
    summary = re.sub(r"(['\"]).*?\1", "<value>", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    file_name = PurePath((failure.file or "unknown").replace("\\", "/")).name.lower()
    material = "|".join(
        (
            failure.framework,
            test_id,
            failure.exception_type or "",
            signature_codes,
            file_name,
            summary,
        )
    )
    return f"ft-{hashlib.sha256(material.encode()).hexdigest()[:12]}"


class UniversalFailureParser:
    """Parse popular ecosystem logs while preserving a generic fallback."""

    def detect_format(self, output: str) -> str:
        if (
            _PYTEST_FAILURE.search(output)
            or (_PYTHON_LOCATION.search(output) and _EXCEPTION.search(output))
            or "pytest" in output.lower()
        ):
            return "pytest"
        if _JEST_FAILURE.search(output) or re.search(r"^Tests:\s+", output, re.M):
            return "jest/vitest"
        if _GO_FAILURE.search(output):
            return "go test"
        if "[ERROR]" in output and (
            "BUILD FAILURE" in output or "Tests run:" in output or "<<< FAILURE!" in output
        ):
            return "maven/gradle"
        if _CONTAINER_FAILURE.search(output) or re.search(
            r"\b(?:kubernetes|kubectl|containerd|docker daemon)\b", output, re.I
        ):
            return "container/platform"
        if _DATABASE_FAILURE.search(output) or re.search(
            r"\b(?:psycopg|postgresql|mysql|sqlite|oracle)\b", output, re.I
        ):
            return "database"
        if _HTTP_FAILURE.search(output) or _NETWORK_FAILURE.search(output):
            return "http/api"
        if _DEPENDENCY_FAILURE.search(output):
            return "dependency"
        if _COMPILER_ERROR.search(output):
            return "compiler"
        if _EXCEPTION.search(output):
            return "runtime"
        if _APPLICATION_FAILURE.search(output):
            return "application"
        return "generic"

    def parse(self, output: str) -> list[Failure]:
        if not output.strip():
            return []

        log_format = self.detect_format(output)
        if log_format == "pytest":
            failures = self._parse_pytest(output)
        elif log_format == "jest/vitest":
            failures = self._parse_jest(output)
        elif log_format == "go test":
            failures = self._parse_go(output)
        elif log_format == "maven/gradle":
            failures = self._parse_java(output)
        elif log_format == "http/api":
            failures = self._parse_http(output)
        elif log_format == "container/platform":
            failures = self._parse_signal(
                output,
                _CONTAINER_FAILURE,
                framework=log_format,
                exception_type="ContainerError",
            )
        elif log_format == "database":
            failures = self._parse_signal(
                output,
                _DATABASE_FAILURE,
                framework=log_format,
                exception_type="DatabaseError",
            )
        elif log_format == "dependency":
            failures = self._parse_signal(
                output,
                _DEPENDENCY_FAILURE,
                framework=log_format,
                exception_type="DependencyError",
            )
        elif log_format == "application":
            failures = self._parse_signal(
                output,
                _APPLICATION_FAILURE,
                framework=log_format,
                exception_type="ApplicationError",
            )
        else:
            failures = self._parse_generic(output, log_format)
        if not failures and _APPLICATION_FAILURE.search(output):
            exception_type = {
                "container/platform": "ContainerError",
                "database": "DatabaseError",
                "dependency": "DependencyError",
            }.get(log_format, "ApplicationError")
            failures = self._parse_signal(
                output,
                _APPLICATION_FAILURE,
                framework=log_format,
                exception_type=exception_type,
            )
        return [
            failure.model_copy(update={"fingerprint": failure_fingerprint(failure)})
            for failure in failures
        ]

    def _parse_pytest(self, output: str) -> list[Failure]:
        locations = list(_PYTHON_LOCATION.finditer(output))
        exceptions = list(_EXCEPTION.finditer(output))
        failures: list[Failure] = []
        for match in _PYTEST_FAILURE.finditer(output):
            test_id = match.group("test")
            summary = (match.group("summary") or "pytest reported a failure").strip()
            file_name = test_id.split("::", 1)[0] if ".py" in test_id else None
            line = self._line_for_file(file_name, locations)
            exception_type = self._exception_from_summary(summary)
            if not exception_type and exceptions:
                exception_type = exceptions[-1].group("type")
                if summary == "pytest reported a failure":
                    detail = (exceptions[-1].group("detail") or "").strip()
                    summary = f"{exception_type}: {detail}".rstrip(": ")
            failures.append(
                Failure(
                    test_id=test_id,
                    summary=summary[:500],
                    file=file_name,
                    line=line,
                    exception_type=exception_type,
                    framework="pytest",
                )
            )
        if failures:
            return failures
        return self._parse_exception_fallback(output, "pytest")

    def _parse_jest(self, output: str) -> list[Failure]:
        files = list(_JEST_FAILURE.finditer(output))
        tests = list(_JEST_TEST.finditer(output))
        locations = list(_JS_LOCATION.finditer(output))
        failures: list[Failure] = []
        for index, match in enumerate(files):
            file_name = match.group("file")
            test_name = tests[index].group("test").strip() if index < len(tests) else file_name
            location = next(
                (item for item in locations if item.group("file").endswith(file_name)),
                locations[0] if locations else None,
            )
            failures.append(
                Failure(
                    test_id=test_name,
                    summary=self._jest_summary(output, test_name),
                    file=file_name,
                    line=int(location.group("line")) if location else None,
                    exception_type="AssertionError" if "Expected:" in output else None,
                    framework="jest/vitest",
                )
            )
        return failures or self._parse_exception_fallback(output, "jest/vitest")

    def _parse_go(self, output: str) -> list[Failure]:
        locations = list(_GO_LOCATION.finditer(output))
        failures: list[Failure] = []
        for index, match in enumerate(_GO_FAILURE.finditer(output)):
            location = locations[index] if index < len(locations) else None
            failures.append(
                Failure(
                    test_id=match.group("test"),
                    summary=(
                        location.group("detail").strip()
                        if location
                        else "go test reported a failure"
                    )[:500],
                    file=location.group("file") if location else None,
                    line=int(location.group("line")) if location else None,
                    framework="go test",
                )
            )
        return failures

    def _parse_java(self, output: str) -> list[Failure]:
        exceptions = list(_EXCEPTION.finditer(output))
        locations = list(_JAVA_LOCATION.finditer(output))
        failures: list[Failure] = []
        for index, match in enumerate(_JAVA_FAILURE.finditer(output)):
            exception = exceptions[index] if index < len(exceptions) else None
            location = locations[index] if index < len(locations) else None
            exception_type = exception.group("type") if exception else None
            detail = (exception.group("detail") or "").strip() if exception else ""
            failures.append(
                Failure(
                    test_id=match.group("test"),
                    summary=(
                        f"{exception_type}: {detail}".rstrip(": ")
                        if exception_type
                        else "Java test reported a failure"
                    )[:500],
                    file=location.group("file") if location else None,
                    line=int(location.group("line")) if location else None,
                    exception_type=exception_type,
                    framework="maven/gradle",
                )
            )
        return failures or self._parse_exception_fallback(output, "maven/gradle")

    def _parse_generic(self, output: str, log_format: str) -> list[Failure]:
        match = _COMPILER_ERROR.search(output)
        if match:
            return [
                Failure(
                    test_id="build-or-compile",
                    summary=match.group("detail").strip()[:500],
                    file=match.group("file").strip(),
                    line=int(match.group("paren_line") or match.group("line")),
                    exception_type="BuildError",
                    framework=log_format,
                )
            ]
        return self._parse_exception_fallback(output, log_format)

    @staticmethod
    def _parse_http(output: str) -> list[Failure]:
        match = _HTTP_FAILURE.search(output)
        network_match = _NETWORK_FAILURE.search(output)
        if not match and not network_match:
            return []
        request = _HTTP_REQUEST.search(output)
        request_path = request.group("path").split("?", 1)[0] if request else ""
        test_id = f"{request.group('method').upper()} {request_path}" if request else "http-request"
        if match:
            detail = match.group("detail").strip(" :-")
            summary = f"HTTP {match.group('status')}"
            if detail:
                summary += f" {detail}"
        else:
            assert network_match is not None
            summary = network_match.group("detail").strip()
        return [
            Failure(
                test_id=test_id,
                summary=summary[:500],
                exception_type="HttpError",
                framework="http/api",
            )
        ]

    @staticmethod
    def _parse_signal(
        output: str,
        pattern: re.Pattern[str],
        *,
        framework: str,
        exception_type: str,
    ) -> list[Failure]:
        match = pattern.search(output)
        if not match:
            return []
        detail = (
            match.groupdict().get("detail")
            or match.groupdict().get("reason")
            or match.group(0)
        )
        return [
            Failure(
                test_id=f"{framework}-incident",
                summary=detail.strip()[:500],
                exception_type=exception_type,
                framework=framework,
            )
        ]

    @staticmethod
    def _parse_exception_fallback(output: str, framework: str) -> list[Failure]:
        exceptions = list(_EXCEPTION.finditer(output))
        if not exceptions:
            return []
        exception = exceptions[-1]
        locations = list(_PYTHON_LOCATION.finditer(output))
        location = locations[-1] if locations else None
        exception_type = exception.group("type")
        detail = (exception.group("detail") or "").strip()
        return [
            Failure(
                test_id=(
                    "collection-or-runtime"
                    if framework == "pytest"
                    else "collection-build-or-runtime"
                ),
                summary=f"{exception_type}: {detail}".rstrip(": ")[:500],
                file=location.group("file").strip() if location else None,
                line=int(location.group("line")) if location else None,
                exception_type=exception_type,
                framework=framework,
            )
        ]

    @staticmethod
    def _line_for_file(file_name: str | None, locations: list[re.Match[str]]) -> int | None:
        if not file_name:
            return None
        normalized = file_name.replace("\\", "/")
        for match in reversed(locations):
            candidate = match.group("file").strip().replace("\\", "/")
            if candidate.endswith(normalized):
                return int(match.group("line"))
        return None

    @staticmethod
    def _exception_from_summary(summary: str) -> str | None:
        match = re.search(r"\b([A-Za-z_][\w.]*(?:Error|Exception))\b", summary)
        return match.group(1) if match else None

    @staticmethod
    def _jest_summary(output: str, test_name: str) -> str:
        expected = re.search(r"^\s*Expected:\s*(.+)$", output, re.M)
        received = re.search(r"^\s*Received:\s*(.+)$", output, re.M)
        if expected and received:
            return (
                f"Expected {expected.group(1).strip()}, received {received.group(1).strip()}"
            )[:500]
        return f"JavaScript test failed: {test_name}"[:500]


class PytestFailureParser(UniversalFailureParser):
    """Backward-compatible name for integrations created before v0.2."""
