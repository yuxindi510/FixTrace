"""FastAPI application for asynchronous FixTrace analyses."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse

from fixtrace import __version__
from fixtrace.core.config import Settings
from fixtrace.core.models import AnalysisRequest, AnalysisTask, TaskStatus
from fixtrace.core.pipeline import AnalysisPipeline
from fixtrace.core.tasks import TaskNotFoundError, TaskStore

settings = Settings.from_env()
task_store = TaskStore()
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fixtrace")
static_root = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="FixTrace",
    version=__version__,
    description="Evidence-driven CI failure reproduction and repair verification.",
)


def _run_task(task_id: str, request: AnalysisRequest) -> None:
    task_store.set_status(task_id, TaskStatus.RUNNING)
    pipeline = AnalysisPipeline(settings)
    try:
        report = pipeline.run(request, on_stage=lambda event: task_store.add_stage(task_id, event))
    except Exception as exc:  # boundary: persist task failure instead of losing the worker
        task_store.fail(task_id, str(exc))
        return
    task_store.succeed(task_id, report)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_root / "index.html")


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "version": __version__,
        "local_execution_enabled": settings.allow_local_execution,
        "local_sources_enabled": settings.allow_local_sources,
    }


@app.post(
    "/api/analyses",
    response_model=AnalysisTask,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis(request: AnalysisRequest) -> AnalysisTask:
    task = task_store.create(request)
    executor.submit(_run_task, task.id, request)
    return task


@app.get("/api/analyses", response_model=list[AnalysisTask])
def list_analyses() -> list[AnalysisTask]:
    return task_store.list()


@app.get("/api/analyses/{task_id}", response_model=AnalysisTask)
def get_analysis(task_id: str) -> AnalysisTask:
    try:
        return task_store.get(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis task not found.") from exc


@app.get("/api/analyses/{task_id}/report")
def get_report(task_id: str) -> Response:
    try:
        task = task_store.get(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis task not found.") from exc
    if not task.report:
        raise HTTPException(status_code=409, detail="Analysis report is not ready.")
    return Response(task.report.markdown, media_type="text/markdown; charset=utf-8")
