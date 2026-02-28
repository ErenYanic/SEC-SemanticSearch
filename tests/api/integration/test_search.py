"""
Integration tests for the ``POST /api/search/`` endpoint.

The ``SearchEngine`` is fully mocked — these tests exercise the route
handler's input validation, error mapping, and response formatting.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_search_engine
from sec_semantic_search.core.exceptions import SearchError
from sec_semantic_search.core.types import ContentType, SearchResult


def _make_client(search_results=None, search_error=None):
    """Build a TestClient with a mocked SearchEngine."""
    engine = MagicMock()
    if search_error:
        engine.search.side_effect = search_error
    else:
        engine.search.return_value = search_results or []
    app.dependency_overrides[get_search_engine] = lambda: engine
    return TestClient(app, raise_server_exceptions=False), engine


def _make_result(**overrides):
    """Create a minimal SearchResult for testing."""
    defaults = dict(
        content="Sample content",
        path="Part I > Item 1",
        content_type=ContentType.TEXT,
        ticker="AAPL",
        form_type="10-K",
        similarity=0.45,
        filing_date="2024-11-01",
        accession_number="0000320193-24-000001",
        chunk_id="AAPL_10-K_2024-11-01_0",
    )
    defaults.update(overrides)
    return SearchResult(**defaults)


class TestSearchEndpoint:
    """POST /api/search/ — semantic search."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_valid_query_with_results(self):
        results = [_make_result()]
        client, _ = _make_client(search_results=results)
        resp = client.post("/api/search/", json={"query": "revenue"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "revenue"
        assert data["total_results"] == 1
        assert data["search_time_ms"] >= 0
        assert data["results"][0]["ticker"] == "AAPL"
        assert data["results"][0]["content_type"] == "text"

    def test_valid_query_no_results(self):
        client, _ = _make_client(search_results=[])
        resp = client.post("/api/search/", json={"query": "obscure query"})
        data = resp.json()
        assert data["total_results"] == 0
        assert data["results"] == []

    def test_empty_query_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/api/search/", json={"query": ""})
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_search_error_empty_returns_400(self):
        error = SearchError("Empty search query")
        client, _ = _make_client(search_error=error)
        resp = client.post("/api/search/", json={"query": "x"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "validation_error"

    def test_search_error_other_returns_500(self):
        error = SearchError("Database unreachable", details="timeout")
        client, _ = _make_client(search_error=error)
        resp = client.post("/api/search/", json={"query": "x"})
        assert resp.status_code == 500
        assert resp.json()["detail"]["error"] == "search_error"

    def test_ticker_filter_passed(self):
        client, engine = _make_client()
        client.post("/api/search/", json={"query": "test", "ticker": "aapl"})
        _, kwargs = engine.search.call_args
        assert kwargs["ticker"] == "AAPL"

    def test_form_type_filter_passed(self):
        client, engine = _make_client()
        client.post("/api/search/", json={"query": "test", "form_type": "10-q"})
        _, kwargs = engine.search.call_args
        assert kwargs["form_type"] == "10-Q"

    def test_invalid_form_type_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/api/search/", json={"query": "test", "form_type": "8-K"})
        assert resp.status_code == 422

    def test_top_k_out_of_range_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/api/search/", json={"query": "test", "top_k": 101})
        assert resp.status_code == 422

    def test_accession_number_passed(self):
        client, engine = _make_client()
        client.post("/api/search/", json={"query": "test", "accession_number": "acc-123"})
        _, kwargs = engine.search.call_args
        assert kwargs["accession_number"] == "acc-123"