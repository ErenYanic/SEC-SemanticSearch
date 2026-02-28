"""
Integration tests for the ingestion endpoints.

Covers task creation (add/batch), listing, status retrieval, and
cancellation. The ``TaskManager`` is mocked — these tests exercise
route-level validation, delegation, and response formatting.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_task_manager
from sec_semantic_search.api.tasks import TaskState
from tests.helpers import make_task_info


def _make_client(task_manager=None):
    """Build a TestClient with a mocked TaskManager."""
    manager = task_manager or MagicMock()
    if task_manager is None:
        manager.create_task.return_value = "abc123def456abc123def456abc123de"
        manager.list_tasks.return_value = []
        manager.get_task.return_value = None
        manager.cancel_task.return_value = False
    app.dependency_overrides[get_task_manager] = lambda: manager
    return TestClient(app, raise_server_exceptions=False), manager


# -----------------------------------------------------------------------
# POST /api/ingest/add
# -----------------------------------------------------------------------


class TestIngestAdd:
    """Single-ticker ingestion."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_single_ticker(self):
        client, manager = _make_client()
        resp = client.post("/api/ingest/add", json={"tickers": ["AAPL"]})
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["websocket_url"].startswith("/ws/ingest/")

    def test_multiple_tickers_returns_400(self):
        client, _ = _make_client()
        resp = client.post("/api/ingest/add", json={"tickers": ["AAPL", "MSFT"]})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "validation_error"

    def test_empty_tickers_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/api/ingest/add", json={"tickers": []})
        assert resp.status_code == 422

    def test_ticker_normalised_uppercase(self):
        client, manager = _make_client()
        client.post("/api/ingest/add", json={"tickers": ["aapl"]})
        call_kwargs = manager.create_task.call_args[1]
        assert call_kwargs["tickers"] == ["AAPL"]

    def test_custom_parameters_passed(self):
        client, manager = _make_client()
        client.post("/api/ingest/add", json={
            "tickers": ["AAPL"],
            "form_types": ["10-K"],
            "count_mode": "per_form",
            "count": 3,
            "year": 2023,
        })
        call_kwargs = manager.create_task.call_args[1]
        assert call_kwargs["form_types"] == ["10-K"]
        assert call_kwargs["count_mode"] == "per_form"
        assert call_kwargs["count"] == 3
        assert call_kwargs["year"] == 2023


# -----------------------------------------------------------------------
# POST /api/ingest/batch
# -----------------------------------------------------------------------


class TestIngestBatch:
    """Multi-ticker ingestion."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_single_ticker(self):
        client, _ = _make_client()
        resp = client.post("/api/ingest/batch", json={"tickers": ["AAPL"]})
        assert resp.status_code == 202

    def test_multiple_tickers(self):
        client, _ = _make_client()
        resp = client.post("/api/ingest/batch", json={"tickers": ["AAPL", "MSFT", "GOOGL"]})
        assert resp.status_code == 202

    def test_empty_tickers_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/api/ingest/batch", json={"tickers": []})
        assert resp.status_code == 422


# -----------------------------------------------------------------------
# GET /api/ingest/tasks
# -----------------------------------------------------------------------


class TestListTasks:
    """List all ingestion tasks."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_empty(self):
        client, _ = _make_client()
        resp = client.get("/api/ingest/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_with_tasks(self):
        manager = MagicMock()
        info = make_task_info(state=TaskState.RUNNING)
        manager.list_tasks.return_value = [info]
        client, _ = _make_client(task_manager=manager)
        data = client.get("/api/ingest/tasks").json()
        assert data["total"] == 1
        assert data["tasks"][0]["status"] == "running"
        assert data["tasks"][0]["tickers"] == ["AAPL"]


# -----------------------------------------------------------------------
# GET /api/ingest/tasks/{task_id}
# -----------------------------------------------------------------------


class TestGetTask:
    """Get individual task status."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_existing(self):
        manager = MagicMock()
        info = make_task_info(state=TaskState.COMPLETED)
        manager.get_task.return_value = info
        client, _ = _make_client(task_manager=manager)
        resp = client.get(f"/api/ingest/tasks/{info.task_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_not_found(self):
        client, _ = _make_client()
        resp = client.get("/api/ingest/tasks/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "not_found"


# -----------------------------------------------------------------------
# DELETE /api/ingest/tasks/{task_id}
# -----------------------------------------------------------------------


class TestCancelTask:
    """Cancel a running or pending task."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_cancel_pending(self):
        manager = MagicMock()
        info = make_task_info(state=TaskState.PENDING)
        manager.get_task.return_value = info
        manager.cancel_task.return_value = True
        client, _ = _make_client(task_manager=manager)
        resp = client.delete(f"/api/ingest/tasks/{info.task_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"

    def test_cancel_finished_returns_409(self):
        manager = MagicMock()
        info = make_task_info(state=TaskState.COMPLETED)
        manager.get_task.return_value = info
        manager.cancel_task.return_value = False
        client, _ = _make_client(task_manager=manager)
        resp = client.delete(f"/api/ingest/tasks/{info.task_id}")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "conflict"

    def test_cancel_not_found(self):
        client, _ = _make_client()
        resp = client.delete("/api/ingest/tasks/nonexistent")
        assert resp.status_code == 404