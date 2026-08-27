"""Parse compact pytest/CI output into normalized failure records."""

from __future__ import annotations

import re

from fixtrace.core.models import Failure

_FAILURE_LINE = re.compile(r"^(?:FAILED|ERROR)\s+(?P<test>\S+?)(?:\s+-\s+(?P<summary>.+))?$", re.M)
_LOCATION_LINE = re.compile(r"^(?P<file>[^\n:]+\.py):(?P<line>\d+)(?::|\s)", re.M)
_EXCEPTION_LINE = re.compile(
    r"^(?:E\s+)?(?P<type>[A-Za-z_][\w.]*(?:Error|Exception))(?::\s*(?P<detail>.*))?$",
    re.M,
)


class PytestFailureParser:
    def parse(self, output: str) -> list[Failure]:
        if not output.strip():
            return []

        locations = list(_LOCATION_LINE.finditer(output))
        exceptions = list(_EXCEPTION_LINE.finditer(output))
        failures: list[Failure] = []
        for match in _FAILURE_LINE.finditer(output):
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
                )
            )

        if failures:
            return failures

        exception = exceptions[-1] if exceptions else None
        if exception:
            location = locations[-1] if locations else None
            exception_type = exception.group("type")
            detail = (exception.group("detail") or "").strip()
            return [
                Failure(
                    test_id="collection-or-runtime",
                    summary=f"{exception_type}: {detail}".rstrip(": ")[:500],
                    file=location.group("file").strip() if location else None,
                    line=int(location.group("line")) if location else None,
                    exception_type=exception_type,
                )
            ]
        return []

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
