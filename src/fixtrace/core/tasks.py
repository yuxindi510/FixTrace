"""Thread-safe in-memory task registry for the MVP web service."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from uuid import uuid4

from fixtrace.core.models import (
    AnalysisReport,
    AnalysisRequest,
    AnalysisTask,
    StageEvent,
    TaskStatus,
    utc_now,
)


class TaskNotFoundError(KeyError):
    pass


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, AnalysisTask] = {}
        self._lock = RLock()

    def create(self, request: AnalysisRequest) -> AnalysisTask:
        task = AnalysisTask(id=uuid4().hex[:12], request=request)
        with self._lock:
            self._tasks[task.id] = task
        return deepcopy(task)

    def get(self, task_id: str) -> AnalysisTask:
        with self._lock:
            try:
                return deepcopy(self._tasks[task_id])
            except KeyError as exc:
                raise TaskNotFoundError(task_id) from exc

    def list(self) -> list[AnalysisTask]:
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda item: item.created_at, reverse=True)
            return deepcopy(tasks)

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        with self._lock:
            task = self._require(task_id)
            task.status = status
            task.updated_at = utc_now()

    def add_stage(self, task_id: str, event: StageEvent) -> None:
        with self._lock:
            task = self._require(task_id)
            task.stages.append(event)
            task.updated_at = utc_now()

    def succeed(self, task_id: str, report: AnalysisReport) -> None:
        with self._lock:
            task = self._require(task_id)
            task.report = report
            task.status = TaskStatus.SUCCEEDED
            task.updated_at = utc_now()

    def fail(self, task_id: str, error: str) -> None:
        with self._lock:
            task = self._require(task_id)
            task.error = error
            task.status = TaskStatus.FAILED
            task.updated_at = utc_now()

    def _require(self, task_id: str) -> AnalysisTask:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFoundError(task_id) from exc
