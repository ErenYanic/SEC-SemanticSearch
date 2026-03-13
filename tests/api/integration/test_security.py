"""
Security tests for vulnerability fixes identified in SECURITY VULNERABILITIES.md.

Each test class maps to a specific finding number from the security audit.
Tests verify that the fix is in place and working correctly.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_chroma, get_registry, get_search_engine
from sec_semantic_search.api.schemas import (
    BulkDeleteRequest,
    DeleteByIdsRequest,
    IngestRequest,
    SearchRequest,
)
from sec_semantic_search.api.tasks import (
    TaskManager,
    TaskQueueFullError,
    TaskState,
)
from sec_semantic_search.core.exceptions import DatabaseError, SearchError
from tests.helpers import make_filing_record, make_task_info


# -----------------------------------------------------------------------
# Finding #1: .env not tracked by git
# -----------------------------------------------------------------------


class TestEnvNotTracked:
    """Verify .env is in .gitignore and not tracked."""

    def test_gitignore_contains_env(self):
        from pathlib import Path

        gitignore = Path(__file__).parents[3] / ".gitignore"
        content = gitignore.read_text()
        assert ".env" in content


# -----------------------------------------------------------------------
# Finding #2: WebSocket origin validation
# -----------------------------------------------------------------------


class TestWebSocketOriginValidation:
    """WebSocket endpoint rejects connections from disallowed origins."""

    def test_allowed_origin_connects(self):
        """Connection from allowed origin should succeed."""
        info = make_task_info(state=TaskState.COMPLETED)
        manager = MagicMock()
        manager.get_task.return_value = info
        app.state.task_manager = manager

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/ingest/{info.task_id}",
            headers={"origin": "http://localhost:3000"},
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"

    def test_no_origin_header_connects(self):
        """Connection without Origin header should be allowed (non-browser clients)."""
        info = make_task_info(state=TaskState.COMPLETED)
        manager = MagicMock()
        manager.get_task.return_value = info
        app.state.task_manager = manager

        client = TestClient(app)
        # TestClient does not send Origin by default — this tests non-browser use.
        with client.websocket_connect(f"/ws/ingest/{info.task_id}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"


# -----------------------------------------------------------------------
# Finding #3: CORS configuration
# -----------------------------------------------------------------------


class TestCORSConfiguration:
    """CORS should use explicit method and header lists."""

    def test_cors_allows_get(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "GET" in resp.headers.get("access-control-allow-methods", "")

    def test_cors_blocks_put(self):
        """PUT should not be in allowed methods."""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PUT",
            },
        )
        # PUT should not appear in allowed methods
        allowed = resp.headers.get("access-control-allow-methods", "")
        assert "PUT" not in allowed


# -----------------------------------------------------------------------
# Finding #5: API binds to 127.0.0.1 by default
# -----------------------------------------------------------------------


class TestDefaultBindAddress:
    """API should default to 127.0.0.1 instead of 0.0.0.0."""

    def test_default_host_is_localhost(self):
        from sec_semantic_search.config.settings import ApiSettings

        settings = ApiSettings()
        assert settings.host == "127.0.0.1"


# -----------------------------------------------------------------------
# Finding #6: Error response information disclosure
# -----------------------------------------------------------------------


class TestErrorRedaction:
    """Error responses must not leak internal details."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_delete_error_redacts_details(self):
        registry = MagicMock()
        record = make_filing_record()
        registry.get_filing.return_value = record

        chroma = MagicMock()
        chroma.delete_filing.side_effect = DatabaseError(
            "SQLite error", details="UNIQUE constraint failed on filings.accession_number"
        )

        app.dependency_overrides[get_registry] = lambda: registry
        app.dependency_overrides[get_chroma] = lambda: chroma
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.delete(f"/api/filings/{record.accession_number}")
        assert resp.status_code == 500
        body = resp.json()["detail"]
        # The internal SQLite error details must NOT be exposed
        assert "UNIQUE constraint" not in body.get("message", "")
        assert body.get("details") is None

    def test_search_error_redacts_details(self):
        engine = MagicMock()
        engine.search.side_effect = SearchError(
            "Internal failure", details="torch.cuda.OutOfMemoryError: CUDA out of memory"
        )

        app.dependency_overrides[get_search_engine] = lambda: engine
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/search/", json={"query": "revenue growth"})
        assert resp.status_code == 500
        body = resp.json()["detail"]
        assert "CUDA" not in body.get("message", "")
        assert body.get("details") is None


# -----------------------------------------------------------------------
# Finding #9: Search query length limit
# -----------------------------------------------------------------------


class TestSearchQueryLengthLimit:
    """Search query must be capped at 2000 characters."""

    def test_query_too_long_rejected(self):
        with pytest.raises(ValidationError, match="at most 2000"):
            SearchRequest(query="x" * 2001)

    def test_query_at_limit_accepted(self):
        req = SearchRequest(query="x" * 2000)
        assert len(req.query) == 2000

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError, match="at least 1"):
            SearchRequest(query="")


# -----------------------------------------------------------------------
# Finding #11: Ticker symbol validation
# -----------------------------------------------------------------------


class TestTickerValidation:
    """Ticker symbols must match [A-Z.]{1,5} format."""

    def test_valid_ticker(self):
        req = SearchRequest(query="test", ticker="AAPL")
        assert req.ticker == "AAPL"

    def test_valid_ticker_with_dot(self):
        req = SearchRequest(query="test", ticker="BRK.B")
        assert req.ticker == "BRK.B"

    def test_ticker_normalised_to_uppercase(self):
        req = SearchRequest(query="test", ticker="aapl")
        assert req.ticker == "AAPL"

    def test_invalid_ticker_path_traversal(self):
        with pytest.raises(ValidationError, match="Invalid ticker"):
            SearchRequest(query="test", ticker="../../../etc/passwd")

    def test_invalid_ticker_too_long(self):
        with pytest.raises(ValidationError, match="Invalid ticker"):
            SearchRequest(query="test", ticker="TOOLONG")

    def test_invalid_ticker_numbers(self):
        with pytest.raises(ValidationError, match="Invalid ticker"):
            SearchRequest(query="test", ticker="123")

    def test_ingest_ticker_validation(self):
        with pytest.raises(ValidationError, match="Invalid ticker"):
            IngestRequest(tickers=["../hack"])

    def test_ingest_valid_tickers(self):
        req = IngestRequest(tickers=["AAPL", "MSFT"])
        assert req.tickers == ["AAPL", "MSFT"]

    def test_bulk_delete_ticker_validation(self):
        with pytest.raises(ValidationError, match="Invalid ticker"):
            BulkDeleteRequest(ticker="../../etc")


# -----------------------------------------------------------------------
# Finding #12: Accession number validation
# -----------------------------------------------------------------------


class TestAccessionNumberValidation:
    """Accession numbers must match NNNNNNNNNN-YY-NNNNNN format."""

    def test_valid_accession_number(self):
        req = SearchRequest(
            query="test", accession_number="0000320193-24-000001"
        )
        assert req.accession_number == "0000320193-24-000001"

    def test_invalid_accession_number(self):
        with pytest.raises(ValidationError, match="Invalid accession"):
            SearchRequest(query="test", accession_number="invalid-format")

    def test_accession_too_long(self):
        with pytest.raises(ValidationError, match="at most 20"):
            SearchRequest(query="test", accession_number="x" * 21)

    def test_delete_by_ids_accession_validation(self):
        with pytest.raises(ValidationError, match="Invalid accession"):
            DeleteByIdsRequest(accession_numbers=["not-valid"])

    def test_delete_by_ids_valid(self):
        req = DeleteByIdsRequest(
            accession_numbers=["0000320193-24-000001"]
        )
        assert len(req.accession_numbers) == 1

    def test_filing_path_param_validation(self):
        """Path parameter must match the accession number format."""
        registry = MagicMock()
        registry.get_filing.return_value = None
        app.dependency_overrides[get_registry] = lambda: registry

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/filings/not-a-valid-accession")
        assert resp.status_code == 422  # Pydantic/FastAPI validation error
        app.dependency_overrides.clear()


# -----------------------------------------------------------------------
# Finding #13: GPU semaphore starvation / task queue cap
# -----------------------------------------------------------------------


class TestTaskQueueCap:
    """Task manager must reject tasks when queue is full."""

    def test_queue_full_raises_error(self):
        registry = MagicMock()
        chroma = MagicMock()
        fetcher = MagicMock()
        orchestrator = MagicMock()

        manager = TaskManager(
            registry=registry,
            chroma=chroma,
            fetcher=fetcher,
            orchestrator=orchestrator,
        )

        # Fill the queue with pending tasks (mock them as pending).
        for i in range(5):
            info = make_task_info(
                task_id=f"task{i:032d}",
                state=TaskState.PENDING,
            )
            manager._tasks[info.task_id] = info

        # The 6th task should be rejected.
        with pytest.raises(TaskQueueFullError, match="queue is full"):
            manager.create_task(tickers=["AAPL"], form_types=["10-K"])

        manager.shutdown()

    def test_queue_allows_after_completion(self):
        registry = MagicMock()
        chroma = MagicMock()
        fetcher = MagicMock()
        orchestrator = MagicMock()

        manager = TaskManager(
            registry=registry,
            chroma=chroma,
            fetcher=fetcher,
            orchestrator=orchestrator,
        )

        # Fill with completed tasks — they should not count.
        for i in range(10):
            info = make_task_info(
                task_id=f"done{i:032d}",
                state=TaskState.COMPLETED,
            )
            manager._tasks[info.task_id] = info

        # Should succeed because completed tasks don't count.
        task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        assert task_id is not None
        manager.shutdown()

    def test_ingest_route_returns_429(self):
        """The ingest route should return 429 when the queue is full."""
        from sec_semantic_search.api.dependencies import get_task_manager

        manager = MagicMock()
        manager.create_task.side_effect = TaskQueueFullError(
            "Task queue is full (5 active)."
        )

        app.dependency_overrides[get_task_manager] = lambda: manager
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/api/ingest/add",
            json={"tickers": ["AAPL"]},
        )
        assert resp.status_code == 429
        assert "queue" in resp.json()["detail"]["message"].lower()
        app.dependency_overrides.clear()


# -----------------------------------------------------------------------
# Finding #16: Security headers
# -----------------------------------------------------------------------


class TestSecurityHeaders:
    """All responses must include security headers."""

    def test_health_check_has_security_headers(self):
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_error_response_has_security_headers(self):
        """404 responses from valid routes should still include security headers."""
        registry = MagicMock()
        registry.get_filing.return_value = None
        app.dependency_overrides[get_registry] = lambda: registry

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/filings/0000320193-24-000001")
        assert resp.status_code == 404
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        app.dependency_overrides.clear()
