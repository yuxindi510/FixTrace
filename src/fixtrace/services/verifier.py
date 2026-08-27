"""Compare before/after logs and make conservative repair-verification decisions."""

from __future__ import annotations

import re

from fixtrace.core.models import Failure, VerificationResult, VerificationStatus
from fixtrace.services.failure_parser import UniversalFailureParser

_PASS_SIGNALS = (
    re.compile(r"\b\d+\s+passed\b", re.I),
    re.compile(r"^Tests:\s+.*\bpassed\b", re.I | re.M),
    re.compile(r"^PASS\s+", re.M),
    re.compile(r"\bBUILD SUCCESS(?:FUL)?\b", re.I),
    re.compile(r"^ok\s+\S+", re.M),
    re.compile(r"\b0\s+failed\b", re.I),
    re.compile(r"HTTP/\d(?:\.\d)?\s+2\d\d\b", re.I),
    re.compile(r"status(?:[_ ]code)?\s*[:=]\s*2\d\d\b", re.I),
    re.compile(
        r"\b(?:health check passed|status healthy|request succeeded|startup complete)\b",
        re.I,
    ),
)


class RepairVerifier:
    def __init__(self, parser: UniversalFailureParser) -> None:
        self.parser = parser

    def verify(self, before: list[Failure], after_output: str) -> VerificationResult:
        before_ids = self._fingerprints(before)
        if not after_output.strip():
            return VerificationResult(before_fingerprints=before_ids)

        after = self.parser.parse(after_output)
        after_ids = self._fingerprints(after)
        before_set = set(before_ids)
        after_set = set(after_ids)
        remaining = sorted(before_set & after_set)
        resolved = sorted(before_set - after_set)
        new = sorted(after_set - before_set)
        pass_signal = any(pattern.search(after_output) for pattern in _PASS_SIGNALS)

        shared = {
            "pass_signal": pass_signal,
            "before_fingerprints": before_ids,
            "after_fingerprints": after_ids,
            "resolved_fingerprints": resolved,
            "remaining_fingerprints": remaining,
            "new_fingerprints": new,
        }
        if not before_ids:
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                summary="The baseline log did not contain a normalized failure to compare.",
                **shared,
            )
        if remaining:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                summary=f"{len(remaining)} original failure fingerprint(s) still appear.",
                **shared,
            )
        if after_ids:
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                summary=(
                    "The original failure disappeared, but the rerun contains "
                    f"{len(after_ids)} different failure fingerprint(s)."
                ),
                **shared,
            )
        if pass_signal:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                summary=(
                    f"All {len(before_ids)} original failure fingerprint(s) disappeared "
                    "and the rerun contains an explicit success signal."
                ),
                **shared,
            )
        return VerificationResult(
            status=VerificationStatus.INCONCLUSIVE,
            summary=(
                "The original failure was not found, but the rerun has no recognized "
                "success signal."
            ),
            **shared,
        )

    @staticmethod
    def _fingerprints(failures: list[Failure]) -> list[str]:
        return sorted({failure.fingerprint for failure in failures if failure.fingerprint})
