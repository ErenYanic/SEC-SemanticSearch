"""
Integration tests for per-session EDGAR credentials (W5.5).

Covers:
    - ``get_edgar_identity()`` dependency: header propagation, env var
      fallback, 401 rejection when neither is available.
    - Ingest routes pass EDGAR identity through to ``TaskManager.create_task()``.
    - Status endpoint exposes ``edgar_session_required`` flag.
    - EDGAR credentials are never logged (privacy invariant).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import (
    EdgarIdentity,
    get_chroma,
    get_edgar_identity,
    get_registry,
    get_task_manager,
)
from sec_semantic_search.database.metadata import DatabaseStatistics


def _make_ingest_client(task_manager=None, override_identity=None):
    """Build a TestClient with a mocked TaskManager.

    When *override_identity* is provided, the ``get_edgar_identity``
    dependency is overridden to return it directly (bypassing header/env
    resolution).
    """
    manager = task_manager or MagicMock()
    if task_manager is None:
        manager.create_task.return_value = "abc123def456abc123def456abc123de"
    app.dependency_overrides[get_task_manager] = lambda: manager
    if override_identity is not None:
        app.dependency_overrides[get_edgar_identity] = lambda: override_identity
    return TestClient(app, raise_server_exceptions=False), manager


def _make_status_client():
    """Build a TestClient for the status endpoint with mocked stores."""
    registry = MagicMock()
    registry.get_statistics.return_value = DatabaseStatistics(
        filing_count=0, tickers=[], form_breakdown={}, ticker_breakdown=[],
    )
    chroma = MagicMock()
    chroma.collection_count.return_value = 0
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chroma] = lambda: chroma
    return TestClient(app, raise_server_exceptions=False)


# -----------------------------------------------------------------------
# get_edgar_identity dependency — unit tests
# -----------------------------------------------------------------------


class TestGetEdgarIdentity:
    """Test the ``get_edgar_identity`` dependency in isolation."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_headers_take_priority_over_env_vars(self):
        """X-Edgar-Name / X-Edgar-Email headers should override env vars."""
        from starlette.testclient import TestClient as _  # noqa: F401

        request = MagicMock()
        request.headers = {
            "X-Edgar-Name": "Header Name",
            "X-Edgar-Email": "header@example.com",
        }

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = "Server Name"
            s.edgar.identity_email = "server@example.com"
            s.api.edgar_session_required = True

            result = await get_edgar_identity(request)
            assert result.name == "Header Name"
            assert result.email == "header@example.com"

    @pytest.mark.anyio
    async def test_falls_back_to_env_vars(self):
        """When no headers, should use server-side env vars."""
        request = MagicMock()
        request.headers = {}

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = "Server Name"
            s.edgar.identity_email = "server@example.com"
            s.api.edgar_session_required = False

            result = await get_edgar_identity(request)
            assert result.name == "Server Name"
            assert result.email == "server@example.com"

    @pytest.mark.anyio
    async def test_401_when_no_credentials_and_required(self):
        """Should raise 401 when session required but no credentials."""
        from fastapi import HTTPException

        request = MagicMock()
        request.headers = {}

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = None
            s.edgar.identity_email = None
            s.api.edgar_session_required = True

            with pytest.raises(HTTPException) as exc_info:
                await get_edgar_identity(request)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "edgar_credentials_required"

    @pytest.mark.anyio
    async def test_401_when_no_credentials_and_not_required(self):
        """Should raise 401 even when not required — no credentials at all."""
        from fastapi import HTTPException

        request = MagicMock()
        request.headers = {}

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = None
            s.edgar.identity_email = None
            s.api.edgar_session_required = False

            with pytest.raises(HTTPException) as exc_info:
                await get_edgar_identity(request)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error"] == "edgar_credentials_missing"

    @pytest.mark.anyio
    async def test_partial_headers_fall_through(self):
        """Only name header without email should fall through to env vars."""
        request = MagicMock()
        request.headers = {"X-Edgar-Name": "Only Name"}

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = "Env Name"
            s.edgar.identity_email = "env@example.com"
            s.api.edgar_session_required = True

            result = await get_edgar_identity(request)
            assert result.name == "Env Name"
            assert result.email == "env@example.com"

    @pytest.mark.anyio
    async def test_header_values_are_stripped(self):
        """Whitespace should be trimmed from header values."""
        request = MagicMock()
        request.headers = {
            "X-Edgar-Name": "  Jane Smith  ",
            "X-Edgar-Email": "  jane@example.com  ",
        }

        with patch(
            "sec_semantic_search.api.dependencies.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = None
            s.edgar.identity_email = None
            s.api.edgar_session_required = True

            result = await get_edgar_identity(request)
            assert result.name == "Jane Smith"
            assert result.email == "jane@example.com"


# -----------------------------------------------------------------------
# Ingest routes — identity passthrough
# -----------------------------------------------------------------------


class TestIngestIdentityPassthrough:
    """Verify that EDGAR identity is forwarded to TaskManager.create_task()."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    def test_identity_passed_to_create_task_via_add(self):
        identity = EdgarIdentity(name="Test User", email="test@example.com")
        client, manager = _make_ingest_client(override_identity=identity)
        resp = client.post("/api/ingest/add", json={"tickers": ["AAPL"]})
        assert resp.status_code == 202

        call_kwargs = manager.create_task.call_args[1]
        assert call_kwargs["edgar_name"] == "Test User"
        assert call_kwargs["edgar_email"] == "test@example.com"

    def test_identity_passed_to_create_task_via_batch(self):
        identity = EdgarIdentity(name="Batch User", email="batch@example.com")
        client, manager = _make_ingest_client(override_identity=identity)
        resp = client.post(
            "/api/ingest/batch", json={"tickers": ["AAPL", "MSFT"]},
        )
        assert resp.status_code == 202

        call_kwargs = manager.create_task.call_args[1]
        assert call_kwargs["edgar_name"] == "Batch User"
        assert call_kwargs["edgar_email"] == "batch@example.com"

    def test_non_ingest_routes_do_not_require_identity(self):
        """Search, filings, status routes should not need EDGAR headers."""
        registry = MagicMock()
        registry.get_statistics.return_value = DatabaseStatistics(
            filing_count=0, tickers=[], form_breakdown={}, ticker_breakdown=[],
        )
        chroma = MagicMock()
        chroma.collection_count.return_value = 0
        app.dependency_overrides[get_registry] = lambda: registry
        app.dependency_overrides[get_chroma] = lambda: chroma

        client = TestClient(app, raise_server_exceptions=False)
        # These should NOT return 401 even without EDGAR headers.
        assert client.get("/api/status/").status_code == 200


# -----------------------------------------------------------------------
# Status endpoint — edgar_session_required flag
# -----------------------------------------------------------------------


class TestStatusEdgarSessionRequired:
    """Verify the ``edgar_session_required`` field in status response."""

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        app.dependency_overrides.clear()

    def test_false_when_server_has_identity(self):
        """Should be false when server-side EDGAR vars are set."""
        client = _make_status_client()
        with patch(
            "sec_semantic_search.api.routes.status.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = "Name"
            s.edgar.identity_email = "email@example.com"
            s.api.edgar_session_required = True
            s.database.max_filings = 500

            data = client.get("/api/status/").json()
            assert data["edgar_session_required"] is False

    def test_true_when_no_server_identity_and_required(self):
        """Should be true when no server-side vars and setting is true."""
        client = _make_status_client()
        with patch(
            "sec_semantic_search.api.routes.status.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = None
            s.edgar.identity_email = None
            s.api.edgar_session_required = True
            s.database.max_filings = 500

            data = client.get("/api/status/").json()
            assert data["edgar_session_required"] is True

    def test_false_when_not_required(self):
        """Should be false when setting is false regardless of env vars."""
        client = _make_status_client()
        with patch(
            "sec_semantic_search.api.routes.status.get_settings"
        ) as mock_settings:
            s = mock_settings.return_value
            s.edgar.identity_name = None
            s.edgar.identity_email = None
            s.api.edgar_session_required = False
            s.database.max_filings = 500

            data = client.get("/api/status/").json()
            assert data["edgar_session_required"] is False


# -----------------------------------------------------------------------
# Privacy — EDGAR credentials never logged
# -----------------------------------------------------------------------


class TestEdgarCredentialsNeverLogged:
    """Ensure EDGAR credentials do not appear in log output."""

    def test_set_identity_does_not_log_email(self):
        """FilingFetcher.set_identity() must not log name or email."""
        with patch(
            "sec_semantic_search.pipeline.fetch.logger"
        ) as mock_logger:
            from sec_semantic_search.pipeline.fetch import FilingFetcher

            with patch.object(FilingFetcher, "__init__", lambda self: None):
                fetcher = FilingFetcher.__new__(FilingFetcher)

            with patch("sec_semantic_search.pipeline.fetch.set_identity"):
                fetcher.set_identity("Sensitive Name", "sensitive@email.com")

            # Check all log calls — none should contain the credentials.
            for call in mock_logger.method_calls:
                call_str = str(call)
                assert "Sensitive Name" not in call_str
                assert "sensitive@email.com" not in call_str

    def test_configure_identity_does_not_log_email(self):
        """FilingFetcher._configure_identity() must not log email."""
        with patch(
            "sec_semantic_search.pipeline.fetch.logger"
        ) as mock_logger, patch(
            "sec_semantic_search.pipeline.fetch.get_settings"
        ) as mock_settings, patch(
            "sec_semantic_search.pipeline.fetch.set_identity"
        ):
            s = mock_settings.return_value
            s.edgar.identity_name = "Secret Name"
            s.edgar.identity_email = "secret@email.com"
            s.database.max_filings = 500

            from sec_semantic_search.pipeline.fetch import FilingFetcher

            with patch.object(FilingFetcher, "__init__", lambda self: None):
                fetcher = FilingFetcher.__new__(FilingFetcher)
            fetcher.settings = s
            fetcher._configure_identity()

            for call in mock_logger.method_calls:
                call_str = str(call)
                assert "Secret Name" not in call_str
                assert "secret@email.com" not in call_str
