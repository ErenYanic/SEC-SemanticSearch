"""
Integration tests for the ``GET /api/status/`` endpoint.

Uses FastAPI's ``TestClient`` with dependency overrides so no real
ChromaDB or SQLite is touched.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_chroma, get_registry
from sec_semantic_search.database.metadata import DatabaseStatistics, TickerStatistics


def _make_stats(
    filing_count=0,
    tickers=None,
    form_breakdown=None,
    ticker_breakdown=None,
):
    """Build a DatabaseStatistics with sensible defaults."""
    return DatabaseStatistics(
        filing_count=filing_count,
        tickers=tickers or [],
        form_breakdown=form_breakdown or {},
        ticker_breakdown=ticker_breakdown or [],
    )


def _make_client(stats=None, chunk_count=0):
    registry = MagicMock()
    registry.get_statistics.return_value = stats or _make_stats()
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
        stats = _make_stats(
            filing_count=1,
            tickers=["AAPL"],
            form_breakdown={"10-K": 1},
            ticker_breakdown=[
                TickerStatistics(ticker="AAPL", filings=1, chunks=100, forms=["10-K"]),
            ],
        )
        client = _make_client(stats=stats, chunk_count=100)
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
        stats = _make_stats(
            filing_count=2,
            tickers=["AAPL", "MSFT"],
            form_breakdown={"10-K": 2},
            ticker_breakdown=[
                TickerStatistics(ticker="AAPL", filings=1, chunks=100, forms=["10-K"]),
                TickerStatistics(ticker="MSFT", filings=1, chunks=100, forms=["10-K"]),
            ],
        )
        client = _make_client(stats=stats, chunk_count=200)
        data = client.get("/api/status/").json()
        assert data["tickers"] == ["AAPL", "MSFT"]

    def test_form_breakdown_multiple_forms(self):
        stats = _make_stats(
            filing_count=3,
            tickers=["AAPL"],
            form_breakdown={"10-K": 1, "10-Q": 2},
            ticker_breakdown=[
                TickerStatistics(ticker="AAPL", filings=3, chunks=300, forms=["10-K", "10-Q"]),
            ],
        )
        client = _make_client(stats=stats, chunk_count=300)
        data = client.get("/api/status/").json()
        assert data["form_breakdown"] == {"10-K": 1, "10-Q": 2}

    def test_ticker_breakdown_forms_list(self):
        stats = _make_stats(
            filing_count=2,
            tickers=["AAPL"],
            form_breakdown={"10-K": 1, "10-Q": 1},
            ticker_breakdown=[
                TickerStatistics(ticker="AAPL", filings=2, chunks=200, forms=["10-K", "10-Q"]),
            ],
        )
        client = _make_client(stats=stats, chunk_count=200)
        data = client.get("/api/status/").json()
        tb = data["ticker_breakdown"][0]
        assert sorted(tb["forms"]) == ["10-K", "10-Q"]
        assert tb["filings"] == 2

    def test_max_filings_from_settings(self):
        client = _make_client()
        data = client.get("/api/status/").json()
        assert data["max_filings"] >= 1
