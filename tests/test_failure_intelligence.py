from pathlib import Path

import pytest
from pydantic import ValidationError

from fixtrace.cli import main
from fixtrace.core.config import Settings
from fixtrace.core.models import AnalysisRequest, VerificationStatus
from fixtrace.core.pipeline import AnalysisPipeline
from fixtrace.services.failure_parser import UniversalFailureParser
from fixtrace.services.redactor import SecretRedactor
from fixtrace.services.verifier import RepairVerifier


def test_parses_jest_and_builds_stable_fingerprint() -> None:
    parser = UniversalFailureParser()
    first = """
FAIL src/price.test.ts
  ● applies member discount
    Expected: 80
    Received: 100
      at src/price.test.ts:12:18
Tests: 1 failed, 4 passed
"""
    second = first.replace("Expected: 80", "Expected: 75").replace(
        "Received: 100", "Received: 95"
    ).replace(":12:18", ":44:18")

    failure = parser.parse(first)[0]
    changed_values = parser.parse(second)[0]

    assert parser.detect_format(first) == "jest/vitest"
    assert failure.test_id == "applies member discount"
    assert failure.file == "src/price.test.ts"
    assert failure.fingerprint.startswith("ft-")
    assert failure.fingerprint == changed_values.fingerprint


def test_parses_go_test_and_compiler_output() -> None:
    parser = UniversalFailureParser()
    go_output = """
--- FAIL: TestTotal (0.00s)
    total_test.go:18: got 12, want 10
FAIL
"""
    compiler_output = "src/index.ts(7,12): error TS2322: Type 'string' is not assignable"

    go_failure = parser.parse(go_output)[0]
    compiler_failure = parser.parse(compiler_output)[0]

    assert go_failure.framework == "go test"
    assert go_failure.line == 18
    assert compiler_failure.exception_type == "BuildError"
    assert compiler_failure.file == "src/index.ts"


def test_parses_maven_failure() -> None:
    output = """
[ERROR] com.example.PriceTest.appliesDiscount -- Time elapsed: 0.01 s <<< FAILURE!
java.lang.AssertionError: expected 80 but was 100
    at com.example.PriceTest.appliesDiscount(PriceTest.java:24)
[INFO] BUILD FAILURE
"""

    parser = UniversalFailureParser()
    failure = parser.parse(output)[0]

    assert parser.detect_format(output) == "maven/gradle"
    assert failure.test_id == "com.example.PriceTest.appliesDiscount"
    assert failure.file == "PriceTest.java"
    assert failure.line == 24


def test_redacts_secrets_before_they_reach_reports(tmp_path: Path) -> None:
    token = "synthetic-demo-secret-value"
    output = f"token={token}\nRuntimeError: request failed"
    redacted = SecretRedactor().redact(output)
    settings = Settings(
        allow_local_execution=False,
        allow_local_sources=False,
        timeout_seconds=30,
        max_output_bytes=50_000,
        work_root=tmp_path / "work",
    )

    report = AnalysisPipeline(settings).run(AnalysisRequest(failure_output=output))

    assert redacted.count >= 1
    assert token not in redacted.text
    assert token not in report.model_dump_json()
    assert report.redaction_count >= 1
    assert "[REDACTED]" not in report.markdown


def test_verifier_distinguishes_verified_recurring_and_new_failures() -> None:
    parser = UniversalFailureParser()
    verifier = RepairVerifier(parser)
    before_output = "FAILED tests/test_total.py::test_total - AssertionError: assert 12 == 10"
    before = parser.parse(before_output)

    verified = verifier.verify(before, "5 passed in 0.10s")
    recurring = verifier.verify(before, before_output)
    new_failure = verifier.verify(
        before,
        "FAILED tests/test_tax.py::test_tax - ValueError: invalid rate",
    )

    assert verified.status == VerificationStatus.VERIFIED
    assert recurring.status == VerificationStatus.FAILED
    assert new_failure.status == VerificationStatus.INCONCLUSIVE
    assert new_failure.new_fingerprints


def test_log_only_pipeline_proves_repair(tmp_path: Path) -> None:
    settings = Settings(
        allow_local_execution=False,
        allow_local_sources=False,
        timeout_seconds=30,
        max_output_bytes=50_000,
        work_root=tmp_path / "work",
    )
    request = AnalysisRequest(
        failure_output="""
FAIL src/price.test.ts
  ● applies member discount
    Expected: 80
    Received: 100
Tests: 1 failed, 4 passed
""",
        verification_output="PASS src/price.test.ts\nTests: 5 passed, 5 total",
    )

    report = AnalysisPipeline(settings).run(request)

    assert report.source_kind == "log"
    assert report.log_format == "jest/vitest"
    assert report.verdict == "repair verified"
    assert report.verification.status == VerificationStatus.VERIFIED
    assert "fingerprint" in report.markdown


def test_verify_cli_is_a_machine_checkable_gate(tmp_path: Path) -> None:
    before = tmp_path / "before.log"
    after = tmp_path / "after.log"
    before.write_text(
        "FAILED tests/test_total.py::test_total - AssertionError: assert 12 == 10",
        encoding="utf-8",
    )
    after.write_text("1 passed in 0.02s", encoding="utf-8")

    exit_code = main(["verify", "--before", str(before), "--after", str(after)])

    assert exit_code == 0


def test_analysis_requires_some_evidence_or_context() -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest()
