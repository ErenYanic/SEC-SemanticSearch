"""
WebSocket endpoint for real-time ingestion progress streaming.

Provides a single WebSocket route at ``/ws/ingest/{task_id}`` that
pushes JSON messages as the background ingestion worker progresses
through the pipeline.

Message types (server → client):
    - ``snapshot``       — current state on connect (for reconnection)
    - ``step``           — pipeline step progress
    - ``filing_done``    — filing successfully ingested
    - ``filing_skipped`` — duplicate detected
    - ``filing_failed``  — processing or storage error
    - ``completed``      — task finished
    - ``failed``         — task failed
    - ``cancelled``      — task cancelled

The client does not send messages after the initial connection.
Disconnecting is handled gracefully — the task continues running
server-side.  Reconnecting sends a fresh snapshot so the client
can catch up.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sec_semantic_search.api.tasks import TaskInfo, TaskState
from sec_semantic_search.config import get_settings
from sec_semantic_search.core import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Terminal message types — close the WebSocket after sending one of these.
_TERMINAL_TYPES = frozenset({"completed", "failed", "cancelled"})


def _build_snapshot(info: TaskInfo) -> dict:
    """
    Build a snapshot message from the current task state.

    Sent immediately on WebSocket connect so a reconnecting client
    can catch up on progress made while it was disconnected.
    """
    return {
        "type": "snapshot",
        "task_id": info.task_id,
        "status": info.state.value,
        "progress": {
            "current_ticker": info.progress.current_ticker,
            "current_form_type": info.progress.current_form_type,
            "step_label": info.progress.step_label,
            "step_index": info.progress.step_index,
            "step_total": info.progress.step_total,
            "filings_done": info.progress.filings_done,
            "filings_total": info.progress.filings_total,
            "filings_skipped": info.progress.filings_skipped,
            "filings_failed": info.progress.filings_failed,
        },
        "results": [
            {
                "ticker": r.ticker,
                "form_type": r.form_type,
                "filing_date": r.filing_date,
                "accession_number": r.accession_number,
                "segments": r.segment_count,
                "chunks": r.chunk_count,
                "time": round(r.duration_seconds, 1),
            }
            for r in info.results
        ],
    }


@router.websocket("/ws/ingest/{task_id}")
async def ingest_progress(websocket: WebSocket, task_id: str) -> None:
    """
    Stream real-time ingestion progress for a specific task.

    On connect, validates the ``Origin`` header against allowed CORS
    origins (WebSocket upgrades are not protected by CORS).  Then sends
    a ``snapshot`` message with the current state and continuously
    forwards messages from the task's internal queue until the task
    reaches a terminal state or the client disconnects.
    """
    # --- Origin validation (WebSocket is not protected by CORS) ----------
    origin = websocket.headers.get("origin")
    allowed_origins = get_settings().api.cors_origins
    if origin is not None and origin not in allowed_origins:
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    await websocket.accept()

    # Retrieve the TaskManager from app state.
    task_manager = websocket.app.state.task_manager
    info = task_manager.get_task(task_id)

    if info is None:
        await websocket.send_json({
            "type": "error",
            "error": f"Task '{task_id}' not found.",
        })
        await websocket.close(code=4404, reason="Task not found")
        return

    # Send current state snapshot (supports reconnection).
    await websocket.send_json(_build_snapshot(info))

    # If the task has already reached a terminal state, send the
    # terminal message and close — no need to stream further.
    if info.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
        terminal_msg = _drain_terminal_message(info)
        if terminal_msg is not None:
            await websocket.send_json(terminal_msg)
        await websocket.close()
        return

    # Stream messages from the task's async queue until terminal or
    # disconnect.  Uses asyncio.wait_for with a 5s safety timeout —
    # normal messages arrive near-instantly via call_soon_threadsafe;
    # the timeout only fires during idle periods (e.g. PENDING state
    # waiting for the GPU semaphore).
    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    info._message_queue.get(), timeout=5.0,
                )
            except asyncio.TimeoutError:
                # No message within timeout — check if the task ended
                # while the queue was empty (e.g. terminal message was
                # already consumed by a previous WebSocket connection).
                if info.state in (
                    TaskState.COMPLETED,
                    TaskState.FAILED,
                    TaskState.CANCELLED,
                ):
                    await _drain_and_send(websocket, info._message_queue)
                    break
                continue

            await websocket.send_json(message)

            if message.get("type") in _TERMINAL_TYPES:
                break

    except WebSocketDisconnect:
        logger.info(
            "WebSocket client disconnected from task %s (task continues)",
            task_id[:8],
        )

    except Exception:
        logger.exception("WebSocket error for task %s", task_id[:8])

    finally:
        # Graceful close — task continues running regardless.
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001 — already closing
            pass


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------


async def _drain_and_send(websocket: WebSocket, q: asyncio.Queue) -> None:
    """Drain all remaining messages from the queue and send them."""
    while not q.empty():
        message = q.get_nowait()
        await websocket.send_json(message)


def _drain_terminal_message(info: TaskInfo) -> dict | None:
    """
    Try to find a terminal message in the queue for an already-finished task.

    Returns the message or None if the queue is empty (the terminal
    message was already consumed by a previous WebSocket connection).
    """
    while not info._message_queue.empty():
        message = info._message_queue.get_nowait()
        if message.get("type") in _TERMINAL_TYPES:
            return message
    return None