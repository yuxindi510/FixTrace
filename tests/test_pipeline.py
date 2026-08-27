from pathlib import Path

from fixtrace.core.config import Settings
from fixtrace.core.models import AnalysisRequest, ExecutionMode, StageName
from fixtrace.core.pipeline import AnalysisPipeline


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        allow_local_execution=False,
        allow_local_sources=True,
        timeout_seconds=30,
        max_output_bytes=50_000,
        work_root=tmp_path / "work",
    )


def test_inspect_pipeline_builds_evidence_report(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pytest"]\n', encoding="utf-8"
    )
    (repository / "logic.py").write_text("def total(): return 120\n", encoding="utf-8")
    output = """
tests/test_logic.py:4: AssertionError
FAILED tests/test_logic.py::test_total - AssertionError: assert 120 == 80
"""
    stages = []

    report = AnalysisPipeline(_settings(tmp_path)).run(
        AnalysisRequest(repository=str(repository), failure_output=output),
        on_stage=stages.append,
    )

    assert report.verdict == "failure evidence parsed"
    assert report.stack.primary_language == "Python"
    assert report.hypotheses[0].id == "hyp-behavior"
    assert stages[-1].stage == StageName.REPORT


def test_local_execution_requires_explicit_opt_in(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pytest"]\n', encoding="utf-8"
    )
    (repository / "test_sample.py").write_text("def test_fail(): assert False\n", encoding="utf-8")
    pipeline = AnalysisPipeline(_settings(tmp_path))

    try:
        pipeline.run(
            AnalysisRequest(repository=str(repository), execution_mode=ExecutionMode.LOCAL)
        )
    except RuntimeError as exc:
        assert "Local execution is disabled" in str(exc)
    else:
        raise AssertionError("Expected local execution to be rejected")


def test_local_execution_reproduces_failure_when_opted_in(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pytest"]\n', encoding="utf-8"
    )
    (repository / "test_sample.py").write_text("def test_fail(): assert 2 == 3\n", encoding="utf-8")
    pipeline = AnalysisPipeline(_settings(tmp_path), allow_local_execution=True)

    report = pipeline.run(
        AnalysisRequest(repository=str(repository), execution_mode=ExecutionMode.LOCAL)
    )

    assert report.verdict == "failure reproduced"
    assert report.command_result is not None
    assert report.command_result.exit_code == 1
    assert "/" not in report.command_result.command[0]
