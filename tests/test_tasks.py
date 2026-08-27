import pytest

from fixtrace.core.models import AnalysisRequest, StageEvent, StageName, TaskStatus
from fixtrace.core.tasks import TaskNotFoundError, TaskStore


def test_task_store_lifecycle() -> None:
    store = TaskStore()
    task = store.create(AnalysisRequest(repository="https://github.com/example/project"))

    store.set_status(task.id, TaskStatus.RUNNING)
    store.add_stage(
        task.id,
        StageEvent(stage=StageName.INTAKE, status="completed", message="ready"),
    )

    updated = store.get(task.id)
    assert updated.status == TaskStatus.RUNNING
    assert updated.stages[0].message == "ready"


def test_task_store_returns_copies() -> None:
    store = TaskStore()
    task = store.create(AnalysisRequest(repository="https://github.com/example/project"))
    task.status = TaskStatus.FAILED

    assert store.get(task.id).status == TaskStatus.QUEUED


def test_missing_task_raises_domain_error() -> None:
    with pytest.raises(TaskNotFoundError):
        TaskStore().get("missing")
