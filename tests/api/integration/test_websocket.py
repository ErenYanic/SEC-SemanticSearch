"""
Integration tests for the WebSocket progress endpoint.

Uses FastAPI TestClient's ``websocket_connect()`` with task state
injected directly onto ``app.state.task_manager``.
"""

import queue
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.tasks import TaskState
from tests.helpers import make_task_info


def _make_client_with_task(task_info=None):
    """Build a TestClient with a task manager that returns the given task."""
    manager = MagicMock()
    if task_info is not None:
        manager.get_task.return_value = task_info
    else:
        manager.get_task.return_value = None

    # Inject directly onto app.state (WebSocket reads from app.state,
    # not from dependency overrides).
    app.state.task_manager = manager
    return TestClient(app)


# -----------------------------------------------------------------------
# Connection handling
# -----------------------------------------------------------------------


class TestWebSocketConnect:
    """WebSocket connection and error handling."""

    def test_nonexistent_task(self):
        client = _make_client_with_task(task_info=None)
        with client.websocket_connect("/ws/ingest/nonexistent") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["error"].lower()


class TestWebSocketSnapshot:
    """Snapshot message is sent on connect."""

    def test_pending_task_receives_snapshot(self):
        info = make_task_info(state=TaskState.PENDING)
        client = _make_client_with_task(task_info=info)

        # Put a cancelled message to terminate the loop.
        info._message_queue.put({"type": "cancelled"})

        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["task_id"] == info.task_id
            assert snapshot["status"] == "pending"
            assert "progress" in snapshot


class TestWebSocketCompleted:
    """Already-completed tasks send snapshot + terminal message."""

    def test_completed_task(self):
        info = make_task_info(state=TaskState.COMPLETED)
        # Push a terminal message into the queue.
        info._message_queue.put({
            "type": "completed",
            "results": [],
            "summary": {"total": 0},
        })

        client = _make_client_with_task(task_info=info)
        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot"

            terminal = ws.receive_json()
            assert terminal["type"] == "completed"


class TestWebSocketStreaming:
    """Messages streamed in order during an active task."""

    def test_step_then_terminal(self):
        info = make_task_info(state=TaskState.RUNNING)
        info._message_queue.put({
            "type": "step",
            "ticker": "AAPL",
            "form_type": "10-K",
            "step": "Embedding",
            "step_number": 4,
            "total_steps": 5,
        })
        info._message_queue.put({
            "type": "completed",
            "results": [],
            "summary": {"total": 0},
        })

        client = _make_client_with_task(task_info=info)
        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            snapshot = ws.receive_json()
            assert snapshot["type"] == "snapshot"

            step = ws.receive_json()
            assert step["type"] == "step"
            assert step["step"] == "Embedding"

            completed = ws.receive_json()
            assert completed["type"] == "completed"

    def test_filing_done_message(self):
        info = make_task_info(state=TaskState.RUNNING)
        info._message_queue.put({
            "type": "filing_done",
            "ticker": "AAPL",
            "form_type": "10-K",
            "filing_date": "2024-11-01",
            "accession_number": "acc-1",
            "segments": 100,
            "chunks": 110,
            "time": 5.3,
        })
        info._message_queue.put({"type": "completed", "results": [], "summary": {}})

        client = _make_client_with_task(task_info=info)
        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            ws.receive_json()  # snapshot
            filing_done = ws.receive_json()
            assert filing_done["type"] == "filing_done"
            assert filing_done["ticker"] == "AAPL"
            assert filing_done["chunks"] == 110

    def test_cancelled_message(self):
        info = make_task_info(state=TaskState.RUNNING)
        info._message_queue.put({"type": "cancelled"})

        client = _make_client_with_task(task_info=info)
        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            ws.receive_json()  # snapshot
            msg = ws.receive_json()
            assert msg["type"] == "cancelled"