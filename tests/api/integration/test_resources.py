"""
Integration tests for the GPU resource management endpoints.

Covers ``GET /api/resources/gpu`` (model status) and
``DELETE /api/resources/gpu`` (model unload).
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_embedder, get_task_manager


def _make_client(is_loaded=False, device="cuda", vram=None, has_active=False):
    """Build a TestClient with mocked embedder and task manager."""
    embedder = MagicMock()
    embedder.is_loaded = is_loaded
    embedder.device = device
    embedder.model_name = "test-model"
    embedder.approximate_vram_mb = vram

    manager = MagicMock()
    manager.has_active_task.return_value = has_active

    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_task_manager] = lambda: manager
    return TestClient(app, raise_server_exceptions=False), embedder, manager


# -----------------------------------------------------------------------
# GET /api/resources/gpu
# -----------------------------------------------------------------------


class TestGPUStatus:
    """GET /api/resources/gpu — model status."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_not_loaded(self):
        client, *_ = _make_client(is_loaded=False)
        resp = client.get("/api/resources/gpu")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_loaded"] is False
        assert data["device"] is None
        assert data["approximate_vram_mb"] is None
        assert data["model_name"] == "test-model"

    def test_loaded_on_cuda(self):
        client, *_ = _make_client(is_loaded=True, device="cuda", vram=1200)
        data = client.get("/api/resources/gpu").json()
        assert data["model_loaded"] is True
        assert data["device"] == "cuda"
        assert data["approximate_vram_mb"] == 1200

    def test_loaded_on_cpu(self):
        client, *_ = _make_client(is_loaded=True, device="cpu", vram=None)
        data = client.get("/api/resources/gpu").json()
        assert data["model_loaded"] is True
        assert data["device"] == "cpu"
        assert data["approximate_vram_mb"] is None


# -----------------------------------------------------------------------
# DELETE /api/resources/gpu
# -----------------------------------------------------------------------


class TestGPUUnload:
    """DELETE /api/resources/gpu — model unload."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_unload_loaded_model(self):
        client, embedder, _ = _make_client(is_loaded=True)
        resp = client.delete("/api/resources/gpu")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unloaded"
        embedder.unload.assert_called_once()

    def test_unload_already_unloaded(self):
        client, embedder, _ = _make_client(is_loaded=False)
        resp = client.delete("/api/resources/gpu")
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_unloaded"
        embedder.unload.assert_not_called()

    def test_unload_with_active_task_returns_409(self):
        client, embedder, _ = _make_client(is_loaded=True, has_active=True)
        resp = client.delete("/api/resources/gpu")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "Conflict"
        embedder.unload.assert_not_called()