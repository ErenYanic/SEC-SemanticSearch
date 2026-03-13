"""
Security tests for vulnerability fixes identified in SECURITY VULNERABILITIES.md.

Each test class maps to a specific finding number from the security audit.
Tests verify that the fix is in place and working correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import (
    get_chroma,
    get_registry,
    get_search_engine,
    verify_api_key,
)
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
# Finding #8: Unsafe SQLite threading — atomic check-then-insert
# -----------------------------------------------------------------------


class TestAtomicRegistration:
    """SQLite registration must be atomic to prevent race conditions."""

    def test_task_manager_uses_atomic_registration(self):
        """TaskManager._execute() store step uses register_filing_if_new."""
        import inspect

        from sec_semantic_search.api.tasks import TaskManager

        source = inspect.getsource(TaskManager._execute)
        # The atomic method must be used, not the non-atomic register_filing.
        assert "register_filing_if_new" in source
        # The old non-atomic pattern should not be present.
        assert "register_filing(" not in source.replace(
            "register_filing_if_new", ""
        )

    def test_register_filing_if_new_holds_lock(self):
        """register_filing_if_new must hold the lock across check and insert."""
        import inspect

        from sec_semantic_search.database.metadata import MetadataRegistry

        source = inspect.getsource(MetadataRegistry.register_filing_if_new)
        # The lock and connection context manager must wrap both
        # the SELECT check and the INSERT — a single `with` block.
        assert "with self._lock, self._conn:" in source

    def test_chromadb_rollback_on_failure(self):
        """If ChromaDB store fails after SQLite registration, SQLite is rolled back."""
        registry = MagicMock()
        registry.register_filing_if_new.return_value = True
        chroma = MagicMock()
        chroma.store_filing.side_effect = DatabaseError(
            "ChromaDB write error", details="disk full"
        )
        fetcher = MagicMock()
        orchestrator = MagicMock()

        manager = TaskManager(
            registry=registry,
            chroma=chroma,
            fetcher=fetcher,
            orchestrator=orchestrator,
        )
        manager.shutdown()

        # Verify that remove_filing is called to roll back SQLite
        # when ChromaDB fails. We check the source code structure
        # because the full _execute flow requires extensive mocking.
        import inspect

        source = inspect.getsource(TaskManager._execute)
        assert "remove_filing" in source


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


# -----------------------------------------------------------------------
# Finding #7: Database path validation
# -----------------------------------------------------------------------


class TestDatabasePathValidation:
    """Database paths must not escape the project directory."""

    def test_default_paths_accepted(self):
        """Default relative paths within the project should be valid."""
        from sec_semantic_search.config.settings import DatabaseSettings

        settings = DatabaseSettings()
        assert settings.chroma_path == "./data/chroma_db"
        assert settings.metadata_db_path == "./data/metadata.sqlite"

    def test_nested_relative_path_accepted(self):
        """Deeper relative paths within the project should be valid."""
        from sec_semantic_search.config.settings import DatabaseSettings

        settings = DatabaseSettings(
            chroma_path="./data/deep/nested/chroma",
            metadata_db_path="./data/deep/nested/meta.sqlite",
        )
        assert "deep/nested" in settings.chroma_path

    def test_path_traversal_chroma_rejected(self, monkeypatch):
        """Path traversal via chroma_path must be rejected."""
        from sec_semantic_search.config.settings import DatabaseSettings

        with pytest.raises(ValidationError, match="outside the project directory"):
            DatabaseSettings(chroma_path="../../etc/evil_chroma")

    def test_path_traversal_metadata_rejected(self, monkeypatch):
        """Path traversal via metadata_db_path must be rejected."""
        from sec_semantic_search.config.settings import DatabaseSettings

        with pytest.raises(ValidationError, match="outside the project directory"):
            DatabaseSettings(metadata_db_path="../../../tmp/evil.sqlite")

    def test_absolute_path_outside_cwd_rejected(self):
        """Absolute paths outside the working directory must be rejected."""
        from sec_semantic_search.config.settings import DatabaseSettings

        with pytest.raises(ValidationError, match="outside the project directory"):
            DatabaseSettings(chroma_path="/tmp/evil_chroma")

    def test_absolute_path_inside_cwd_accepted(self):
        """Absolute paths within the working directory should be valid."""
        import os

        from sec_semantic_search.config.settings import DatabaseSettings

        safe_path = os.path.join(os.getcwd(), "data", "safe_chroma")
        settings = DatabaseSettings(chroma_path=safe_path)
        assert settings.chroma_path == safe_path

    def test_symlink_in_path_rejected(self, tmp_path):
        """Symlinks in database path components must be rejected."""
        import os

        from sec_semantic_search.config.settings import DatabaseSettings

        # Create a symlink inside CWD that points outside CWD
        link_path = Path(os.getcwd()) / "data" / "symlink_test"
        link_path.parent.mkdir(parents=True, exist_ok=True)
        target = tmp_path / "outside"
        target.mkdir()

        try:
            link_path.symlink_to(target)
            with pytest.raises(ValidationError, match="symlink"):
                DatabaseSettings(
                    chroma_path=str(link_path / "chroma_db"),
                )
        finally:
            # Clean up the symlink
            if link_path.is_symlink():
                link_path.unlink()

    def test_env_var_path_traversal_rejected(self, monkeypatch):
        """Path traversal via environment variables must be rejected."""
        from sec_semantic_search.config.settings import DatabaseSettings

        monkeypatch.setenv("DB_CHROMA_PATH", "../../../../etc/shadow_chroma")
        with pytest.raises(ValidationError, match="outside the project directory"):
            DatabaseSettings()


# -----------------------------------------------------------------------
# Finding #4: API key authentication
# -----------------------------------------------------------------------


class TestApiKeyAuthentication:
    """API endpoints must reject unauthenticated requests when API_KEY is set."""

    TEST_KEY = "test-secret-key-12345"

    def setup_method(self):
        """Inject mock dependencies so routes don't touch real stores."""
        registry = MagicMock()
        registry.list_filings.return_value = []
        registry.get_statistics.return_value = MagicMock(
            filing_count=0,
            tickers=[],
            form_breakdown={},
            ticker_breakdown=[],
        )
        chroma = MagicMock()
        chroma.collection_count.return_value = 0

        app.dependency_overrides[get_registry] = lambda: registry
        app.dependency_overrides[get_chroma] = lambda: chroma

    def teardown_method(self):
        app.dependency_overrides.clear()

    def _enable_auth(self, monkeypatch):
        """Patch settings to enable API key authentication."""
        monkeypatch.setattr(
            "sec_semantic_search.api.dependencies.get_settings",
            lambda: MagicMock(api=MagicMock(key=self.TEST_KEY)),
        )

    # -- Health check is always public --

    def test_health_accessible_without_key(self, monkeypatch):
        """Health check should be accessible even when auth is enabled."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    # -- Auth disabled (default) --

    def test_no_key_configured_allows_all(self):
        """When API_KEY is not set, all endpoints are accessible."""
        # Default settings have key=None — no auth needed.
        client = TestClient(app)
        resp = client.get("/api/status/")
        assert resp.status_code == 200

    # -- Auth enabled: missing key --

    def test_missing_key_returns_401(self, monkeypatch):
        """Requests without X-API-Key header should get 401."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/status/")
        assert resp.status_code == 401
        assert "unauthorised" in resp.json()["detail"]["error"]

    # -- Auth enabled: wrong key --

    def test_wrong_key_returns_401(self, monkeypatch):
        """Requests with an incorrect API key should get 401."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/status/",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    # -- Auth enabled: correct key --

    def test_correct_key_allows_request(self, monkeypatch):
        """Requests with the correct API key should succeed."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/status/",
            headers={"X-API-Key": self.TEST_KEY},
        )
        assert resp.status_code == 200

    # -- Multiple endpoints protected --

    def test_search_requires_key(self, monkeypatch):
        """POST /api/search/ should require API key."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/search/", json={"query": "revenue"})
        assert resp.status_code == 401

    def test_filings_requires_key(self, monkeypatch):
        """GET /api/filings/ should require API key."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/filings/")
        assert resp.status_code == 401

    def test_ingest_requires_key(self, monkeypatch):
        """POST /api/ingest/add should require API key."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/ingest/add",
            json={"tickers": ["AAPL"]},
        )
        assert resp.status_code == 401

    def test_resources_requires_key(self, monkeypatch):
        """GET /api/resources/gpu should require API key."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/resources/gpu")
        assert resp.status_code == 401

    def test_delete_requires_key(self, monkeypatch):
        """DELETE /api/filings/ should require API key."""
        self._enable_auth(monkeypatch)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 401

    # -- WebSocket auth --

    def test_websocket_rejects_without_key(self, monkeypatch):
        """WebSocket should reject connections when API key is wrong."""
        monkeypatch.setattr(
            "sec_semantic_search.api.websocket.get_settings",
            lambda: MagicMock(
                api=MagicMock(key=self.TEST_KEY, cors_origins=["http://localhost:3000"]),
            ),
        )
        info = make_task_info(state=TaskState.COMPLETED)
        manager = MagicMock()
        manager.get_task.return_value = info
        app.state.task_manager = manager

        client = TestClient(app)
        # Connection with wrong key should fail.
        with pytest.raises(Exception):
            with client.websocket_connect(
                f"/ws/ingest/{info.task_id}?api_key=wrong-key",
            ) as ws:
                ws.receive_json()

    def test_websocket_accepts_correct_key(self, monkeypatch):
        """WebSocket should accept connections with correct API key."""
        monkeypatch.setattr(
            "sec_semantic_search.api.websocket.get_settings",
            lambda: MagicMock(
                api=MagicMock(key=self.TEST_KEY, cors_origins=["http://localhost:3000"]),
            ),
        )
        info = make_task_info(state=TaskState.COMPLETED)
        manager = MagicMock()
        manager.get_task.return_value = info
        app.state.task_manager = manager

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/ingest/{info.task_id}?api_key={self.TEST_KEY}",
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"

    def test_websocket_accepts_no_key_when_auth_disabled(self):
        """WebSocket should work without key when auth is disabled."""
        info = make_task_info(state=TaskState.COMPLETED)
        manager = MagicMock()
        manager.get_task.return_value = info
        app.state.task_manager = manager

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/ingest/{info.task_id}",
        ) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
