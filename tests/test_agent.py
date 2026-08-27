import json
from pathlib import Path

import pytest

from fixtrace.agent.runtime import AgentRunner
from fixtrace.core.config import Settings
from fixtrace.core.models import (
    AgentMode,
    AgentStatus,
    AnalysisRequest,
    Evidence,
    Failure,
    IncidentProfile,
    StackProfile,
    VerificationResult,
    VerificationStatus,
)
from fixtrace.core.pipeline import AnalysisPipeline
from fixtrace.services.redactor import SecretRedactor


class ScriptedModel:
    provider = "test"
    model = "scripted-agent"

    def __init__(self, responses: list[dict]) -> None:
        self.responses = [json.dumps(item) for item in responses]
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


def _action(action: str, *, arguments: dict | None = None) -> dict:
    return {
        "action": action,
        "reason": f"Use {action} to ground the investigation.",
        "arguments": arguments or {},
        "summary": "",
        "findings": [],
    }


def _finalize(*, evidence_ids: list[str], observation_ids: list[str] | None = None) -> dict:
    return {
        "action": "finalize",
        "reason": "The available evidence is sufficient for a bounded conclusion.",
        "arguments": {},
        "summary": "The failure is consistent with an incorrect total calculation.",
        "findings": [
            {
                "title": "Incorrect total calculation",
                "explanation": "The failing assertion and implementation return disagree.",
                "confidence": 0.88,
                "evidence_ids": evidence_ids,
                "observation_ids": observation_ids or [],
                "next_actions": ["Correct the calculation and rerun the focused test."],
            }
        ],
    }


def _runner(model: ScriptedModel, *, max_steps: int = 6) -> AgentRunner:
    return AgentRunner(
        model,
        max_steps=max_steps,
        max_tool_output_chars=8_000,
        redactor=SecretRedactor(),
    )


def _run(runner: AgentRunner, repository: Path):
    return runner.run(
        repository_root=repository,
        repository=repository.name,
        stack=StackProfile(primary_language="Python", languages=["Python"]),
        incident=IncidentProfile(),
        failures=[
            Failure(
                test_id="test_total",
                summary="assert 120 == 80",
                file="test_total.py",
                line=4,
                fingerprint="ft-demo",
            )
        ],
        evidence=[
            Evidence(
                id="ev-1",
                kind="test_failure",
                title="test_total",
                detail="assert 120 == 80",
                source="pytest output",
                confidence=0.95,
            )
        ],
        failure_output="FAILED test_total.py::test_total - assert 120 == 80",
        verification=VerificationResult(),
    )


def test_agent_uses_read_only_tools_then_returns_cited_findings(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "logic.py").write_text(
        "def total():\n    return 120\n", encoding="utf-8"
    )
    model = ScriptedModel(
        [
            _action("list_files", arguments={"path": ".", "max_depth": 2}),
            _action("search_source", arguments={"query": "return 120", "path": "."}),
            _action(
                "read_source",
                arguments={"path": "logic.py", "start_line": 1, "end_line": 20},
            ),
            _finalize(evidence_ids=["ev-1"], observation_ids=["obs-3"]),
        ]
    )

    result = _run(_runner(model), repository)

    assert result.status == AgentStatus.COMPLETED
    assert [step.action for step in result.steps] == [
        "list_files",
        "search_source",
        "read_source",
        "finalize",
    ]
    assert "return 120" in result.observations[2].detail
    assert result.findings[0].observation_ids == ["obs-3"]


def test_agent_rejects_repository_escape_without_leaking_file(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    secret = "outside-secret-must-not-leak"
    (tmp_path / "secret.txt").write_text(secret, encoding="utf-8")
    model = ScriptedModel(
        [
            _action("read_source", arguments={"path": "../secret.txt"}),
            _finalize(evidence_ids=["ev-1"]),
        ]
    )

    result = _run(_runner(model), repository)

    assert result.status == AgentStatus.COMPLETED
    assert result.observations[0].ok is False
    assert "escapes" in result.observations[0].detail
    assert secret not in result.model_dump_json()


def test_agent_rejects_unknown_citations_and_requests_correction(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    model = ScriptedModel(
        [
            _finalize(evidence_ids=["ev-invented"]),
            _finalize(evidence_ids=["ev-1"]),
        ]
    )

    result = _run(_runner(model), repository)

    assert result.status == AgentStatus.COMPLETED
    assert result.observations[0].tool == "citation_validator"
    assert result.observations[0].ok is False
    assert result.findings[0].evidence_ids == ["ev-1"]


def test_agent_stops_at_configured_step_limit(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    model = ScriptedModel([_action("list_files"), _action("list_files")])

    result = _run(_runner(model, max_steps=2), repository)

    assert result.status == AgentStatus.MAX_STEPS
    assert result.model_calls == 2


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        allow_local_execution=False,
        allow_local_sources=False,
        timeout_seconds=30,
        max_output_bytes=50_000,
        work_root=tmp_path / "work",
    )


def test_required_agent_fails_when_no_provider_is_configured(tmp_path: Path) -> None:
    pipeline = AnalysisPipeline(_settings(tmp_path))

    with pytest.raises(RuntimeError, match="not_configured"):
        pipeline.run(
            AnalysisRequest(
                failure_output="RuntimeError: request failed",
                agent_mode=AgentMode.REQUIRED,
            )
        )


def test_pipeline_redacts_secrets_before_model_calls(tmp_path: Path) -> None:
    secret = "synthetic-agent-secret-value"
    model = ScriptedModel([_finalize(evidence_ids=["ev-failure-1"])])
    report = AnalysisPipeline(_settings(tmp_path), agent_model=model).run(
        AnalysisRequest(failure_output=f"password={secret}\nRuntimeError: request failed")
    )

    sent = json.dumps(model.calls)
    assert report.agent.status == AgentStatus.COMPLETED
    assert secret not in sent
    assert secret not in report.model_dump_json()
    assert report.verification.status.value == "pending"


def test_agent_cannot_override_deterministic_verification(tmp_path: Path) -> None:
    model = ScriptedModel([_finalize(evidence_ids=["ev-failure-1"])])
    before = "FAILED tests/test_total.py::test_total - AssertionError: assert 12 == 10"
    report = AnalysisPipeline(_settings(tmp_path), agent_model=model).run(
        AnalysisRequest(failure_output=before, verification_output=before)
    )

    assert report.agent.status == AgentStatus.COMPLETED
    assert report.verification.status == VerificationStatus.FAILED
    assert report.verdict == "repair not verified"
