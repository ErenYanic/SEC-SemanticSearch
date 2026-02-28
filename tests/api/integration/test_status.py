"""
Integration tests for the ``GET /api/status/`` endpoint.

Uses FastAPI's ``TestClient`` with dependency overrides so no real
ChromaDB or SQLite is touched.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_chroma, get_registry
from tests.helpers import make_filing_record


def _client(registry_mock, chroma_mock):
    """Build a TestClient with overridden dependencies."""
    app.dependency_overrides[get_registry] = lambda: registry_mock
    app.dependency_overrides[get_chroma] = lambda: chroma_mock
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_client(filings=None, chunk_count=0):
    registry = MagicMock()
    registry.list_filings.return_value = filings or []
    chroma = MagicMock()
    chroma.collection_count.return_value = chunk_count
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chroma] = lambda: chroma
    client = TestClient(app, raise_server_exceptions=False)
    return client


class TestStatusEndpoint:
    """GET /api/status/ — database overview."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_empty_database(self):
        client = _make_client()
        resp = client.get("/api/status/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filing_count"] == 0
        assert data["chunk_count"] == 0
        assert data["tickers"] == []
        assert data["form_breakdown"] == {}
        assert data["ticker_breakdown"] == []

    def test_single_filing(self):
        filings = [make_filing_record(ticker="AAPL", form_type="10-K", chunk_count=100)]
        client = _make_client(filings=filings, chunk_count=100)
        resp = client.get("/api/status/")
        data = resp.json()
        assert data["filing_count"] == 1
        assert data["chunk_count"] == 100
        assert data["tickers"] == ["AAPL"]
        assert data["form_breakdown"] == {"10-K": 1}
        assert len(data["ticker_breakdown"]) == 1
        assert data["ticker_breakdown"][0]["ticker"] == "AAPL"
        assert data["ticker_breakdown"][0]["filings"] == 1
        assert data["ticker_breakdown"][0]["chunks"] == 100

    def test_multiple_tickers_sorted(self):
        filings = [
            make_filing_record(id=1, ticker="MSFT", accession_number="acc-1"),
            make_filing_record(id=2, ticker="AAPL", accession_number="acc-2"),
        ]
        client = _make_client(filings=filings, chunk_count=200)
        data = client.get("/api/status/").json()
        assert data["tickers"] == ["AAPL", "MSFT"]

    def test_form_breakdown_multiple_forms(self):
        filings = [
            make_filing_record(id=1, form_type="10-K", accession_number="acc-1"),
            make_filing_record(id=2, form_type="10-Q", accession_number="acc-2", filing_date="2024-06-01"),
            make_filing_record(id=3, form_type="10-Q", accession_number="acc-3", filing_date="2024-03-01"),
        ]
        client = _make_client(filings=filings, chunk_count=300)
        data = client.get("/api/status/").json()
        assert data["form_breakdown"] == {"10-K": 1, "10-Q": 2}

    def test_ticker_breakdown_forms_list(self):
        filings = [
            make_filing_record(id=1, form_type="10-K", accession_number="acc-1"),
            make_filing_record(id=2, form_type="10-Q", accession_number="acc-2", filing_date="2024-06-01"),
        ]
        client = _make_client(filings=filings, chunk_count=200)
        data = client.get("/api/status/").json()
        tb = data["ticker_breakdown"][0]
        assert sorted(tb["forms"]) == ["10-K", "10-Q"]
        assert tb["filings"] == 2

    def test_max_filings_from_settings(self):
        client = _make_client()
        data = client.get("/api/status/").json()
        assert data["max_filings"] >= 1