"""
Integration tests for W5.6 — Access Control & Abuse Prevention.

Covers:
    - Two-tier API key (admin key validation, permission matrix)
    - DEMO_MODE "clear all" disabled (403 for everyone)
    - ``is_admin`` and ``demo_mode`` in status response
    - Request caps (MAX_TICKERS_PER_REQUEST, MAX_FILINGS_PER_REQUEST)
    - Per-IP ingest cooldown
    - GPU time limit (threading.Timer triggers cancel_event)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import (
    get_chroma,
    get_embedder,
    get_registry,
    get_task_manager,
    is_admin_request,
    verify_api_key,
    verify_admin_key,
)
from sec_semantic_search.api.tasks import TaskInfo, TaskState
from tests.helpers import make_filing_record, make_task_info


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_client(filings=None, chunk_count=0, get_filing_result=None):
    """Build a TestClient with mocked registry and chroma."""
    registry = MagicMock()
    registry.list_filings.return_value = filings or []
    registry.get_filing.return_value = get_filing_result
    registry.get_statistics.return_value = MagicMock(
        filing_count=len(filings or []),
        tickers=["AAPL"],
        form_breakdown={"10-K": 1},
        ticker_breakdown=[],
    )

    chroma = MagicMock()
    chroma.collection_count.return_value = chunk_count
    chroma.delete_filing.return_value = None

    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chroma] = lambda: chroma
    return TestClient(app, raise_server_exceptions=False), registry, chroma


# -----------------------------------------------------------------------
# Two-tier API key — admin key validation
# -----------------------------------------------------------------------


class TestAdminKeyValidation:
    """Test the ``verify_admin_key`` dependency."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_no_admin_key_configured_allows_all(self, mock_settings):
        """When ADMIN_API_KEY is unset, admin operations are unrestricted."""
        mock_settings.return_value.api.admin_key = None
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        # bulk-delete should work without any admin key
        resp = client.post(
            "/api/filings/bulk-delete",
            json={"ticker": "AAPL"},
        )
        assert resp.status_code == 200

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_admin_key_required_rejects_without_header(self, mock_settings):
        """When ADMIN_API_KEY is set, requests without admin key get 403."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.post(
            "/api/filings/bulk-delete",
            json={"ticker": "AAPL"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["error"] == "admin_required"

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_admin_key_required_rejects_wrong_key(self, mock_settings):
        """Wrong admin key is rejected with 403."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.post(
            "/api/filings/bulk-delete",
            json={"ticker": "AAPL"},
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_admin_key_required_allows_correct_key(self, mock_settings):
        """Correct admin key grants access to admin operations."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.post(
            "/api/filings/bulk-delete",
            json={"ticker": "AAPL"},
            headers={"X-Admin-Key": "secret-admin"},
        )
        assert resp.status_code == 200

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_clear_all_requires_admin_key(self, mock_settings):
        """DELETE /api/filings/?confirm=true requires admin key when set."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        client, *_ = _make_client()
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 403

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_gpu_unload_requires_admin_key(self, mock_settings):
        """DELETE /api/resources/gpu requires admin key when set."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None

        embedder = MagicMock()
        embedder.is_loaded = True
        app.dependency_overrides[get_embedder] = lambda: embedder

        manager = MagicMock()
        manager.has_active_task.return_value = False
        app.dependency_overrides[get_task_manager] = lambda: manager

        client, *_ = _make_client()
        resp = client.delete("/api/resources/gpu")
        assert resp.status_code == 403

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_gpu_unload_allowed_with_admin_key(self, mock_settings):
        """DELETE /api/resources/gpu succeeds with correct admin key."""
        mock_settings.return_value.api.admin_key = "secret-admin"
        mock_settings.return_value.api.key = None

        embedder = MagicMock()
        embedder.is_loaded = True
        app.dependency_overrides[get_embedder] = lambda: embedder

        manager = MagicMock()
        manager.has_active_task.return_value = False
        app.dependency_overrides[get_task_manager] = lambda: manager

        client, *_ = _make_client()
        resp = client.delete(
            "/api/resources/gpu",
            headers={"X-Admin-Key": "secret-admin"},
        )
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# DEMO_MODE — "clear all" disabled
# -----------------------------------------------------------------------


class TestDemoMode:
    """Test DEMO_MODE restrictions."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("sec_semantic_search.api.routes.filings.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_clear_all_returns_403_in_demo_mode(
        self, mock_dep_settings, mock_route_settings,
    ):
        """Clear all returns 403 for everyone in DEMO_MODE, even with admin key."""
        mock_dep_settings.return_value.api.admin_key = None
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.demo_mode = True

        client, *_ = _make_client()
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["error"] == "demo_mode"

    @patch("sec_semantic_search.api.routes.filings.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_clear_all_returns_403_in_demo_mode_with_admin(
        self, mock_dep_settings, mock_route_settings,
    ):
        """Even an admin cannot clear all in demo mode."""
        mock_dep_settings.return_value.api.admin_key = "secret"
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.demo_mode = True

        client, *_ = _make_client()
        resp = client.delete(
            "/api/filings/?confirm=true",
            headers={"X-Admin-Key": "secret"},
        )
        assert resp.status_code == 403

    @patch("sec_semantic_search.api.routes.filings.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_bulk_delete_still_works_in_demo_mode_with_admin(
        self, mock_dep_settings, mock_route_settings,
    ):
        """Bulk delete (not clear all) works in demo mode with admin key."""
        mock_dep_settings.return_value.api.admin_key = "secret"
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.demo_mode = True

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.post(
            "/api/filings/bulk-delete",
            json={"ticker": "AAPL"},
            headers={"X-Admin-Key": "secret"},
        )
        assert resp.status_code == 200


# -----------------------------------------------------------------------
# Status response — is_admin and demo_mode flags
# -----------------------------------------------------------------------


class TestStatusFlags:
    """Test ``is_admin`` and ``demo_mode`` in the status response."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("sec_semantic_search.api.routes.status.get_settings")
    @patch("sec_semantic_search.api.routes.status.is_admin_request")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_status_includes_is_admin_true(
        self, mock_dep_settings, mock_is_admin, mock_route_settings,
    ):
        """Status includes is_admin=true when admin key matches."""
        mock_dep_settings.return_value.api.key = None
        settings = MagicMock()
        settings.database.max_filings = 500
        settings.api.demo_mode = False
        settings.api.edgar_session_required = False
        settings.edgar.identity_name = "Test"
        settings.edgar.identity_email = "test@example.com"
        mock_route_settings.return_value = settings
        mock_is_admin.return_value = True

        client, *_ = _make_client()
        resp = client.get("/api/status/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is True

    @patch("sec_semantic_search.api.routes.status.get_settings")
    @patch("sec_semantic_search.api.routes.status.is_admin_request")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_status_includes_demo_mode_true(
        self, mock_dep_settings, mock_is_admin, mock_route_settings,
    ):
        """Status includes demo_mode=true when DEMO_MODE is set."""
        mock_dep_settings.return_value.api.key = None
        settings = MagicMock()
        settings.database.max_filings = 500
        settings.api.demo_mode = True
        settings.api.edgar_session_required = False
        settings.edgar.identity_name = "Test"
        settings.edgar.identity_email = "test@example.com"
        mock_route_settings.return_value = settings
        mock_is_admin.return_value = False

        client, *_ = _make_client()
        resp = client.get("/api/status/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["demo_mode"] is True
        assert data["is_admin"] is False


# -----------------------------------------------------------------------
# is_admin_request helper
# -----------------------------------------------------------------------


class TestIsAdminRequest:
    """Unit tests for ``is_admin_request()``."""

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_no_admin_key_configured_returns_true(self, mock_settings):
        """Everyone is admin when no admin key is configured."""
        mock_settings.return_value.api.admin_key = None
        request = MagicMock()
        assert is_admin_request(request) is True

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_matching_key_returns_true(self, mock_settings):
        """Matching admin key returns True."""
        mock_settings.return_value.api.admin_key = "secret"
        request = MagicMock()
        request.headers.get.return_value = "secret"
        assert is_admin_request(request) is True

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_wrong_key_returns_false(self, mock_settings):
        """Wrong admin key returns False."""
        mock_settings.return_value.api.admin_key = "secret"
        request = MagicMock()
        request.headers.get.return_value = "wrong"
        assert is_admin_request(request) is False

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_missing_key_returns_false(self, mock_settings):
        """Missing admin key header returns False."""
        mock_settings.return_value.api.admin_key = "secret"
        request = MagicMock()
        request.headers.get.return_value = None
        assert is_admin_request(request) is False


# -----------------------------------------------------------------------
# Constant-time secret comparison
# -----------------------------------------------------------------------


class TestConstantTimeSecretComparison:
    """Verify auth helpers use constant-time secret comparison."""

    @pytest.mark.anyio
    @patch("sec_semantic_search.api.dependencies.hmac.compare_digest")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    async def test_verify_api_key_uses_compare_digest(
        self, mock_settings, mock_compare_digest,
    ):
        """API key validation should use constant-time comparison."""
        mock_settings.return_value.api.key = "secret-api-key"
        mock_compare_digest.return_value = True

        await verify_api_key(api_key="secret-api-key")

        mock_compare_digest.assert_called_once_with(
            "secret-api-key", "secret-api-key",
        )

    @pytest.mark.anyio
    @patch("sec_semantic_search.api.dependencies.hmac.compare_digest")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    async def test_verify_admin_key_uses_compare_digest(
        self, mock_settings, mock_compare_digest,
    ):
        """Admin key validation should use constant-time comparison."""
        mock_settings.return_value.api.admin_key = "secret-admin-key"
        mock_compare_digest.return_value = True
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.method = "POST"
        request.url.path = "/api/filings/bulk-delete"

        await verify_admin_key(request, admin_key="secret-admin-key")

        mock_compare_digest.assert_called_once_with(
            "secret-admin-key", "secret-admin-key",
        )

    @patch("sec_semantic_search.api.dependencies.hmac.compare_digest")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_is_admin_request_uses_compare_digest(
        self, mock_settings, mock_compare_digest,
    ):
        """Status admin detection should use constant-time comparison."""
        mock_settings.return_value.api.admin_key = "secret-admin-key"
        mock_compare_digest.return_value = True
        request = MagicMock()
        request.headers.get.return_value = "secret-admin-key"

        assert is_admin_request(request) is True
        mock_compare_digest.assert_called_once_with(
            "secret-admin-key", "secret-admin-key",
        )


# -----------------------------------------------------------------------
# Request caps — MAX_TICKERS_PER_REQUEST, MAX_FILINGS_PER_REQUEST
# -----------------------------------------------------------------------


class TestRequestCaps:
    """Test ingest request caps."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def _make_ingest_client(self):
        """Build a client with mocked ingest dependencies."""
        from sec_semantic_search.api.dependencies import get_edgar_identity, EdgarIdentity

        manager = MagicMock()
        manager.create_task.return_value = "test-task-id"
        app.dependency_overrides[get_task_manager] = lambda: manager
        app.dependency_overrides[get_edgar_identity] = lambda: EdgarIdentity(
            name="Test", email="test@example.com",
        )
        # Also mock registry/chroma so the app doesn't complain
        registry = MagicMock()
        registry.get_statistics.return_value = MagicMock(
            filing_count=0, tickers=[], form_breakdown={}, ticker_breakdown=[],
        )
        chroma = MagicMock()
        chroma.collection_count.return_value = 0
        app.dependency_overrides[get_registry] = lambda: registry
        app.dependency_overrides[get_chroma] = lambda: chroma

        return TestClient(app, raise_server_exceptions=False), manager

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_max_tickers_exceeded(self, mock_dep_settings, mock_route_settings):
        """Too many tickers returns 400."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 2
        mock_route_settings.return_value.api.max_filings_per_request = 0
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 0

        client, _ = self._make_ingest_client()
        resp = client.post("/api/ingest/batch", json={
            "tickers": ["AAPL", "MSFT", "GOOGL"],
            "form_types": ["10-K"],
        })
        assert resp.status_code == 400
        assert "Too many tickers" in resp.json()["detail"]["message"]

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_max_tickers_within_limit(self, mock_dep_settings, mock_route_settings):
        """Tickers within limit succeeds."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 5
        mock_route_settings.return_value.api.max_filings_per_request = 0
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 0

        client, _ = self._make_ingest_client()
        resp = client.post("/api/ingest/batch", json={
            "tickers": ["AAPL", "MSFT"],
            "form_types": ["10-K"],
        })
        assert resp.status_code == 202

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_max_filings_exceeded(self, mock_dep_settings, mock_route_settings):
        """Too many filings requested returns 400."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 0
        mock_route_settings.return_value.api.max_filings_per_request = 10
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 0

        client, _ = self._make_ingest_client()
        resp = client.post("/api/ingest/add", json={
            "tickers": ["AAPL"],
            "form_types": ["10-K"],
            "count_mode": "total",
            "count": 50,
        })
        assert resp.status_code == 400
        assert "Too many filings" in resp.json()["detail"]["message"]

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_max_filings_zero_means_unlimited(self, mock_dep_settings, mock_route_settings):
        """MAX_FILINGS_PER_REQUEST=0 means no limit."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 0
        mock_route_settings.return_value.api.max_filings_per_request = 0
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 0

        client, _ = self._make_ingest_client()
        resp = client.post("/api/ingest/add", json={
            "tickers": ["AAPL"],
            "form_types": ["10-K"],
            "count_mode": "total",
            "count": 9999,
        })
        assert resp.status_code == 202


# -----------------------------------------------------------------------
# Per-IP ingest cooldown
# -----------------------------------------------------------------------


class TestIngestCooldown:
    """Test per-IP ingest cooldown enforcement."""

    def teardown_method(self):
        app.dependency_overrides.clear()
        # Reset the module-level cooldown state
        from sec_semantic_search.api.routes import ingest as ingest_mod
        with ingest_mod._cooldown_lock:
            ingest_mod._last_ingest.clear()

    def _make_ingest_client(self):
        from sec_semantic_search.api.dependencies import get_edgar_identity, EdgarIdentity

        manager = MagicMock()
        manager.create_task.return_value = "test-task-id"
        app.dependency_overrides[get_task_manager] = lambda: manager
        app.dependency_overrides[get_edgar_identity] = lambda: EdgarIdentity(
            name="Test", email="test@example.com",
        )
        registry = MagicMock()
        chroma = MagicMock()
        app.dependency_overrides[get_registry] = lambda: registry
        app.dependency_overrides[get_chroma] = lambda: chroma

        return TestClient(app, raise_server_exceptions=False), manager

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_cooldown_blocks_rapid_requests(self, mock_dep_settings, mock_route_settings):
        """Second request within cooldown period is rejected with 429."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 0
        mock_route_settings.return_value.api.max_filings_per_request = 0
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 60

        client, _ = self._make_ingest_client()
        body = {"tickers": ["AAPL"], "form_types": ["10-K"]}

        resp1 = client.post("/api/ingest/add", json=body)
        assert resp1.status_code == 202

        resp2 = client.post("/api/ingest/add", json=body)
        assert resp2.status_code == 429
        assert "cooldown" in resp2.json()["detail"]["error"]

    @patch("sec_semantic_search.api.routes.ingest.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_cooldown_zero_means_disabled(self, mock_dep_settings, mock_route_settings):
        """INGEST_COOLDOWN_SECONDS=0 means no cooldown."""
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.max_tickers_per_request = 0
        mock_route_settings.return_value.api.max_filings_per_request = 0
        mock_route_settings.return_value.api.ingest_cooldown_seconds = 0

        client, _ = self._make_ingest_client()
        body = {"tickers": ["AAPL"], "form_types": ["10-K"]}

        resp1 = client.post("/api/ingest/add", json=body)
        assert resp1.status_code == 202

        resp2 = client.post("/api/ingest/add", json=body)
        assert resp2.status_code == 202


# -----------------------------------------------------------------------
# GPU time limit
# -----------------------------------------------------------------------


class TestGPUTimeLimit:
    """Test GPU time limit via threading.Timer."""

    def test_timeout_sets_cancel_event(self):
        """_timeout_task sets cancel_event on a running task."""
        from sec_semantic_search.api.tasks import TaskManager

        info = make_task_info(state=TaskState.RUNNING)
        assert not info.cancel_event.is_set()

        TaskManager._timeout_task(info)

        assert info.cancel_event.is_set()

    def test_timeout_ignores_completed_task(self):
        """_timeout_task does nothing if the task already completed."""
        from sec_semantic_search.api.tasks import TaskManager

        info = make_task_info(state=TaskState.COMPLETED)
        TaskManager._timeout_task(info)
        assert not info.cancel_event.is_set()

    def test_timeout_ignores_cancelled_task(self):
        """_timeout_task does nothing if the task is already cancelled."""
        from sec_semantic_search.api.tasks import TaskManager

        info = make_task_info(state=TaskState.CANCELLED)
        TaskManager._timeout_task(info)
        assert not info.cancel_event.is_set()


# -----------------------------------------------------------------------
# Permission matrix — Scenario A (no keys) unrestricted
# -----------------------------------------------------------------------


class TestScenarioAUnrestricted:
    """Verify that Scenario A (no keys set) is fully unrestricted."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_bulk_delete_unrestricted(self, mock_settings):
        """Bulk delete works without any key in Scenario A."""
        mock_settings.return_value.api.admin_key = None
        mock_settings.return_value.api.key = None
        mock_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.post("/api/filings/bulk-delete", json={"ticker": "AAPL"})
        assert resp.status_code == 200

    @patch("sec_semantic_search.api.routes.filings.get_settings")
    @patch("sec_semantic_search.api.dependencies.get_settings")
    def test_clear_all_unrestricted(self, mock_dep_settings, mock_route_settings):
        """Clear all works without any key in Scenario A."""
        mock_dep_settings.return_value.api.admin_key = None
        mock_dep_settings.return_value.api.key = None
        mock_route_settings.return_value.api.demo_mode = False

        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 200
