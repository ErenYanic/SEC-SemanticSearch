"""
Integration tests for the filing management endpoints.

Covers listing, retrieval, single delete, bulk delete, and clear all.
Dependencies are mocked via ``app.dependency_overrides``.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from sec_semantic_search.api.app import app
from sec_semantic_search.api.dependencies import get_chroma, get_registry
from sec_semantic_search.core.exceptions import DatabaseError
from tests.helpers import make_filing_record


def _make_client(filings=None, chunk_count=0, get_filing_result=None):
    """Build a TestClient with mocked registry and chroma."""
    registry = MagicMock()
    registry.list_filings.return_value = filings or []
    registry.get_filing.return_value = get_filing_result

    chroma = MagicMock()
    chroma.collection_count.return_value = chunk_count
    chroma.delete_filing.return_value = 50  # default chunks deleted

    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_chroma] = lambda: chroma
    return TestClient(app, raise_server_exceptions=False), registry, chroma


# -----------------------------------------------------------------------
# GET /api/filings/
# -----------------------------------------------------------------------


class TestListFilings:
    """List filings with optional filters and sorting."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_empty(self):
        client, *_ = _make_client()
        resp = client.get("/api/filings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filings"] == []
        assert data["total"] == 0

    def test_with_filings(self):
        filings = [make_filing_record()]
        client, *_ = _make_client(filings=filings)
        data = client.get("/api/filings/").json()
        assert data["total"] == 1
        assert data["filings"][0]["ticker"] == "AAPL"

    def test_filter_by_ticker(self):
        client, registry, _ = _make_client()
        client.get("/api/filings/?ticker=aapl")
        registry.list_filings.assert_called_with(ticker="AAPL", form_type=None)

    def test_filter_by_form_type(self):
        client, registry, _ = _make_client()
        client.get("/api/filings/?form_type=10-q")
        registry.list_filings.assert_called_with(ticker=None, form_type="10-Q")

    def test_sort_by_ticker_asc(self):
        filings = [
            make_filing_record(id=1, ticker="MSFT", accession_number="acc-1"),
            make_filing_record(id=2, ticker="AAPL", accession_number="acc-2"),
        ]
        client, *_ = _make_client(filings=filings)
        data = client.get("/api/filings/?sort_by=ticker&order=asc").json()
        tickers = [f["ticker"] for f in data["filings"]]
        assert tickers == ["AAPL", "MSFT"]


# -----------------------------------------------------------------------
# GET /api/filings/{accession}
# -----------------------------------------------------------------------


class TestGetFiling:
    """Retrieve a single filing by accession number."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_existing(self):
        record = make_filing_record()
        client, *_ = _make_client(get_filing_result=record)
        resp = client.get("/api/filings/0000320193-24-000001")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    def test_not_found(self):
        client, *_ = _make_client(get_filing_result=None)
        resp = client.get("/api/filings/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "not_found"


# -----------------------------------------------------------------------
# DELETE /api/filings/{accession}
# -----------------------------------------------------------------------


class TestDeleteFiling:
    """Delete a single filing."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_existing(self):
        record = make_filing_record(chunk_count=50)
        client, _, chroma = _make_client(get_filing_result=record)
        chroma.delete_filing.return_value = 50
        resp = client.delete("/api/filings/0000320193-24-000001")
        assert resp.status_code == 200
        assert resp.json()["chunks_deleted"] == 50

    def test_not_found(self):
        client, *_ = _make_client(get_filing_result=None)
        resp = client.delete("/api/filings/nonexistent")
        assert resp.status_code == 404

    def test_database_error(self):
        record = make_filing_record()
        client, _, chroma = _make_client(get_filing_result=record)
        chroma.delete_filing.side_effect = DatabaseError("disk full", details="ENOSPC")
        resp = client.delete("/api/filings/0000320193-24-000001")
        assert resp.status_code == 500
        assert resp.json()["detail"]["error"] == "database_error"


# -----------------------------------------------------------------------
# POST /api/filings/bulk-delete
# -----------------------------------------------------------------------


class TestBulkDelete:
    """Bulk delete filings by filter."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_by_ticker(self):
        filings = [make_filing_record()]
        client, registry, chroma = _make_client()
        registry.list_filings.return_value = filings
        chroma.delete_filing.return_value = 100
        resp = client.post("/api/filings/bulk-delete", json={"ticker": "AAPL"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["filings_deleted"] == 1
        assert data["chunks_deleted"] == 100
        assert data["tickers_affected"] == ["AAPL"]

    def test_no_filters_returns_400(self):
        client, *_ = _make_client()
        resp = client.post("/api/filings/bulk-delete", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "validation_error"

    def test_no_matching_filings(self):
        client, *_ = _make_client()
        resp = client.post("/api/filings/bulk-delete", json={"ticker": "XYZ"})
        assert resp.status_code == 200
        assert resp.json()["filings_deleted"] == 0

    def test_database_error(self):
        filings = [make_filing_record()]
        client, registry, chroma = _make_client()
        registry.list_filings.return_value = filings
        chroma.delete_filing.side_effect = DatabaseError("fail")
        resp = client.post("/api/filings/bulk-delete", json={"ticker": "AAPL"})
        assert resp.status_code == 500


# -----------------------------------------------------------------------
# DELETE /api/filings/?confirm=true
# -----------------------------------------------------------------------


class TestClearAll:
    """Clear all filings from the database."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_without_confirm(self):
        client, *_ = _make_client()
        resp = client.delete("/api/filings/")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "confirmation_required"

    def test_confirm_empty_database(self):
        client, *_ = _make_client()
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 200
        assert resp.json()["filings_deleted"] == 0

    def test_confirm_with_filings(self):
        filings = [
            make_filing_record(id=1, accession_number="acc-1"),
            make_filing_record(id=2, accession_number="acc-2", filing_date="2024-06-01"),
        ]
        client, registry, chroma = _make_client()
        registry.list_filings.return_value = filings
        chroma.delete_filing.return_value = 50
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filings_deleted"] == 2
        assert data["chunks_deleted"] == 100  # 50 * 2

    def test_database_error(self):
        filings = [make_filing_record()]
        client, registry, chroma = _make_client()
        registry.list_filings.return_value = filings
        chroma.delete_filing.side_effect = DatabaseError("fail")
        resp = client.delete("/api/filings/?confirm=true")
        assert resp.status_code == 500