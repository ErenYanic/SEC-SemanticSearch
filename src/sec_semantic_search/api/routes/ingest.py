"""
Ingestion endpoints for starting, monitoring, and cancelling filing ingests.

Provides five routes:
    - ``POST /``           — start single-ticker ingestion
    - ``POST /batch``      — start multi-ticker ingestion
    - ``GET /tasks``       — list all tasks (active + recent)
    - ``GET /tasks/{id}``  — get task status and progress
    - ``DELETE /tasks/{id}`` — cancel a running task

All business logic lives in ``tasks.TaskManager``; these routes are a
thin HTTP layer that validates input, delegates to the manager, and
converts internal dataclasses into Pydantic response schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sec_semantic_search.api.dependencies import get_task_manager
from sec_semantic_search.api.schemas import (
    ErrorResponse,
    IngestRequest,
    IngestResultSchema,
    TaskListResponse,
    TaskProgress as TaskProgressSchema,
    TaskResponse,
    TaskStatus,
)
from sec_semantic_search.api.tasks import TaskInfo, TaskManager
from sec_semantic_search.core import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _task_info_to_status(info: TaskInfo) -> TaskStatus:
    """Convert an internal ``TaskInfo`` dataclass to the API ``TaskStatus`` schema."""
    return TaskStatus(
        task_id=info.task_id,
        status=info.state.value,
        tickers=info.tickers,
        form_types=info.form_types,
        progress=TaskProgressSchema(
            current_ticker=info.progress.current_ticker,
            current_form_type=info.progress.current_form_type,
            step_label=info.progress.step_label,
            step_index=info.progress.step_index,
            step_total=info.progress.step_total,
            filings_done=info.progress.filings_done,
            filings_total=info.progress.filings_total,
            filings_skipped=info.progress.filings_skipped,
            filings_failed=info.progress.filings_failed,
        ),
        results=[
            IngestResultSchema(
                ticker=r.ticker,
                form_type=r.form_type,
                filing_date=r.filing_date,
                accession_number=r.accession_number,
                segment_count=r.segment_count,
                chunk_count=r.chunk_count,
                duration_seconds=r.duration_seconds,
            )
            for r in info.results
        ],
        error=info.error,
        started_at=info.started_at,
        completed_at=info.completed_at,
    )


def _create_task(body: IngestRequest, manager: TaskManager) -> TaskResponse:
    """Shared logic for both add and batch endpoints."""
    task_id = manager.create_task(
        tickers=body.tickers,
        form_types=body.form_types,
        count_mode=body.count_mode,
        count=body.count,
        year=body.year,
        start_date=body.start_date,
        end_date=body.end_date,
    )

    logger.info(
        "Ingest task %s created: tickers=%s, forms=%s, mode=%s",
        task_id[:8],
        body.tickers,
        body.form_types,
        body.count_mode,
    )

    return TaskResponse(
        task_id=task_id,
        status="pending",
        websocket_url=f"/ws/ingest/{task_id}",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/add",
    response_model=TaskResponse,
    status_code=202,
    responses={400: {"model": ErrorResponse}},
    summary="Ingest filings for a single ticker",
)
async def ingest_add(
    body: IngestRequest,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """
    Start an ingestion task for a single ticker symbol.

    The task runs in the background — use the returned ``task_id`` to
    poll status via ``GET /tasks/{task_id}`` or connect to the WebSocket
    at the returned ``websocket_url`` for real-time progress.

    Only one ticker is accepted.  For multiple tickers, use
    ``POST /batch`` instead.
    """
    if len(body.tickers) != 1:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "The /add endpoint accepts exactly one ticker.",
                "details": f"Received {len(body.tickers)} tickers: {body.tickers}",
                "hint": "Use POST /api/ingest/batch for multi-ticker ingestion.",
            },
        )

    return _create_task(body, manager)


@router.post(
    "/batch",
    response_model=TaskResponse,
    status_code=202,
    responses={400: {"model": ErrorResponse}},
    summary="Ingest filings for multiple tickers",
)
async def ingest_batch(
    body: IngestRequest,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskResponse:
    """
    Start an ingestion task for one or more ticker symbols.

    Equivalent to ``sec-search ingest batch``.  The task runs in the
    background; poll status or connect via WebSocket.
    """
    return _create_task(body, manager)


@router.get(
    "/tasks",
    response_model=TaskListResponse,
    summary="List all ingestion tasks",
)
async def list_tasks(
    manager: TaskManager = Depends(get_task_manager),
) -> TaskListResponse:
    """
    Return all ingestion tasks, including active, completed, failed,
    and cancelled tasks that have not yet been pruned (1-hour TTL).
    """
    tasks = manager.list_tasks()
    statuses = [_task_info_to_status(t) for t in tasks]

    return TaskListResponse(tasks=statuses, total=len(statuses))


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatus,
    responses={404: {"model": ErrorResponse}},
    summary="Get ingestion task status",
)
async def get_task(
    task_id: str,
    manager: TaskManager = Depends(get_task_manager),
) -> TaskStatus:
    """
    Return the current status and progress of a specific ingestion task.

    Includes per-filing results as they complete, progress counters,
    and any error messages.
    """
    info = manager.get_task(task_id)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Task '{task_id}' not found.",
                "details": None,
                "hint": "The task may have been pruned after completion (1-hour TTL).",
            },
        )

    return _task_info_to_status(info)


@router.delete(
    "/tasks/{task_id}",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Cancel a running ingestion task",
)
async def cancel_task(
    task_id: str,
    manager: TaskManager = Depends(get_task_manager),
) -> dict[str, str]:
    """
    Request cancellation of a running or pending ingestion task.

    Cancellation is cooperative — the worker thread checks the cancel
    flag between pipeline steps and rolls back any partially stored
    filings.
    """
    info = manager.get_task(task_id)
    if info is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Task '{task_id}' not found.",
                "details": None,
                "hint": "The task may have been pruned after completion (1-hour TTL).",
            },
        )

    cancelled = manager.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": f"Task '{task_id}' has already finished ({info.state.value}).",
                "details": None,
                "hint": "Only pending or running tasks can be cancelled.",
            },
        )

    logger.info("Cancel requested for task %s via API", task_id[:8])
    return {"task_id": task_id, "status": "cancelling"}