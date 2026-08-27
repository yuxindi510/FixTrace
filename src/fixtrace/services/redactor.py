"""Remove common credentials from logs before parsing, storage, or reporting."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    count: int


class SecretRedactor:
    """Conservative secret redaction for developer-tool output."""

    _PATTERNS = (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(
            r"(?im)(?P<prefix>\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|"
            r"client[_-]?secret|secret|token|trace[_-]?id|request[_-]?id|"
            r"correlation[_-]?id)\b\s*[:=]\s*)(?P<quote>['\"]?)"
            r"(?P<value>[^\s'\",;]{4,})(?P=quote)"
        ),
    )

    def redact(self, value: str) -> RedactionResult:
        text = value
        count = 0
        for pattern in self._PATTERNS:
            if "prefix" in pattern.groupindex:
                text, replacements = pattern.subn(
                    lambda match: f"{match.group('prefix')}[REDACTED]",
                    text,
                )
            else:
                text, replacements = pattern.subn("[REDACTED]", text)
            count += replacements
        return RedactionResult(text=text, count=count)
