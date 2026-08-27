"""Opt-in local pytest execution with timeout and credential minimization."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from fixtrace.core.models import CommandResult


class ExecutionDisabledError(RuntimeError):
    pass


class UnsupportedTestRunnerError(RuntimeError):
    pass


class LocalTestRunner:
    def __init__(self, *, enabled: bool, timeout_seconds: int, max_output_bytes: int) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def run(self, root: Path, command: list[str] | None) -> CommandResult:
        if not self.enabled:
            raise ExecutionDisabledError(
                "Local execution is disabled. Set FIXTRACE_ALLOW_LOCAL_EXECUTION=1 only for "
                "repositories you trust, or paste CI output and use inspect mode."
            )
        if not command or command[1:4] != ["-m", "pytest", "-q"]:
            raise UnsupportedTestRunnerError("The MVP currently executes pytest projects only.")

        started = time.monotonic()
        environment = {
            "CI": "1",
            "LANG": os.getenv("LANG", "C.UTF-8"),
            "LC_ALL": os.getenv("LC_ALL", "C.UTF-8"),
            "PATH": os.getenv("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout_seconds,
            )
            stdout, stdout_truncated = self._truncate(completed.stdout)
            stderr, stderr_truncated = self._truncate(completed.stderr)
            return CommandResult(
                command=self._display_command(command),
                exit_code=completed.returncode,
                duration_seconds=round(time.monotonic() - started, 3),
                stdout=stdout,
                stderr=stderr,
                truncated=stdout_truncated or stderr_truncated,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, stdout_truncated = self._truncate(self._as_text(exc.stdout))
            stderr, stderr_truncated = self._truncate(self._as_text(exc.stderr))
            return CommandResult(
                command=self._display_command(command),
                exit_code=124,
                duration_seconds=round(time.monotonic() - started, 3),
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                truncated=stdout_truncated or stderr_truncated,
            )

    @staticmethod
    def _as_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value

    def _truncate(self, value: str) -> tuple[str, bool]:
        raw = value.encode("utf-8", errors="replace")
        if len(raw) <= self.max_output_bytes:
            return value, False
        suffix = "\n\n[FixTrace truncated command output]"
        truncated = raw[: self.max_output_bytes].decode("utf-8", errors="ignore") + suffix
        return truncated, True

    @staticmethod
    def _display_command(command: list[str]) -> list[str]:
        return [Path(command[0]).name, *command[1:]]
