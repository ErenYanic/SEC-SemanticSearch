"""
Tests for the deeper optimisations (F1, F2, F14).

Covers:
    - F1: ``FilingInfo._filing_obj`` caching and ``fetch_filing_content()``
    - F2: Batched ``delete_filings_batch()`` — both stores
    - F14: ``get_filings_by_accessions()`` and ``remove_filings_batch()``
"""

import sqlite3
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.database import delete_filings_batch
from sec_semantic_search.database.metadata import MetadataRegistry
from sec_semantic_search.core import DatabaseError, FilingIdentifier
from sec_semantic_search.pipeline.fetch import FilingFetcher, FilingInfo
from tests.helpers import make_filing_record


# -----------------------------------------------------------------------
# F1: FilingInfo._filing_obj and fetch_filing_content()
# -----------------------------------------------------------------------


class TestFilingInfoCachedObject:
    """FilingInfo stores the edgartools Filing object for direct content fetch."""

    def test_filing_obj_defaults_to_none(self):
        info = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
        )
        assert info._filing_obj is None

    def test_filing_obj_set_explicitly(self):
        mock_filing = MagicMock()
        info = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=mock_filing,
        )
        assert info._filing_obj is mock_filing

    def test_filing_obj_excluded_from_repr(self):
        mock_filing = MagicMock()
        info = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=mock_filing,
        )
        assert "_filing_obj" not in repr(info)

    def test_filing_obj_excluded_from_equality(self):
        """Two FilingInfo objects are equal even if _filing_obj differs."""
        info1 = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=MagicMock(),
        )
        info2 = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=None,
        )
        assert info1 == info2


class TestFetchFilingContent:
    """fetch_filing_content() uses cached object or falls back."""

    @patch.object(FilingFetcher, "__init__", lambda self: None)
    def test_uses_cached_filing_object(self):
        """When _filing_obj is present, fetches directly without EDGAR round-trip."""
        fetcher = FilingFetcher()
        fetcher._fetcher = None  # Suppress attribute errors

        mock_filing = MagicMock()
        mock_filing.html.return_value = "<html>10-K content</html>"
        mock_filing.accession_no = "0000320193-24-000001"
        mock_filing.filing_date = date(2024, 1, 1)

        info = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=mock_filing,
        )

        filing_id, html = fetcher.fetch_filing_content(info)

        assert html == "<html>10-K content</html>"
        assert filing_id.ticker == "AAPL"
        assert filing_id.form_type == "10-K"
        mock_filing.html.assert_called_once()

    @patch.object(FilingFetcher, "__init__", lambda self: None)
    def test_fallback_to_fetch_by_accession(self):
        """When _filing_obj is None, falls back to fetch_by_accession."""
        fetcher = FilingFetcher()

        info = FilingInfo(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
            company_name="Apple Inc.",
            _filing_obj=None,
        )

        mock_id = FilingIdentifier(
            ticker="AAPL",
            form_type="10-K",
            filing_date=date(2024, 1, 1),
            accession_number="0000320193-24-000001",
        )
        fetcher.fetch_by_accession = MagicMock(
            return_value=(mock_id, "<html>fallback</html>"),
        )

        filing_id, html = fetcher.fetch_filing_content(info)

        assert html == "<html>fallback</html>"
        fetcher.fetch_by_accession.assert_called_once_with(
            "AAPL", "10-K", "0000320193-24-000001",
        )

    @patch.object(FilingFetcher, "__init__", lambda self: None)
    def test_list_available_populates_filing_obj(self):
        """list_available() stores the edgartools Filing object on FilingInfo."""
        fetcher = FilingFetcher()
        fetcher.max_filings = 500

        mock_filing = MagicMock()
        mock_filing.accession_no = "0000320193-24-000001"
        mock_filing.filing_date = date(2024, 1, 1)
        mock_filing.company = "Apple Inc."

        fetcher._validate_form_type = MagicMock(return_value="10-K")
        fetcher._get_company = MagicMock()
        fetcher._get_filings = MagicMock(return_value=[mock_filing])
        fetcher._parse_filing_date = MagicMock(return_value=date(2024, 1, 1))

        result = fetcher.list_available("AAPL", "10-K", count=1)

        assert len(result) == 1
        assert result[0]._filing_obj is mock_filing


# -----------------------------------------------------------------------
# F2: Batched delete_filings_batch()
# -----------------------------------------------------------------------


class TestBatchedDeleteFilingsBatch:
    """delete_filings_batch() uses batch methods on both stores."""

    def test_calls_batch_methods(self):
        records = [
            make_filing_record(id=1, accession_number="ACC-001", chunk_count=50),
            make_filing_record(id=2, accession_number="ACC-002", chunk_count=30),
        ]
        chroma = MagicMock()
        registry = MagicMock()

        total = delete_filings_batch(records, chroma=chroma, registry=registry)

        assert total == 80
        chroma.delete_filings_batch.assert_called_once_with(
            ["ACC-001", "ACC-002"],
        )
        registry.remove_filings_batch.assert_called_once_with(
            ["ACC-001", "ACC-002"],
        )

    def test_chromadb_called_before_sqlite(self):
        """Batch deletion maintains ChromaDB-first convention."""
        record = make_filing_record(accession_number="ACC-001")
        call_order = []

        chroma = MagicMock()
        chroma.delete_filings_batch.side_effect = lambda accs: (
            call_order.append("chroma")
        )
        registry = MagicMock()
        registry.remove_filings_batch.side_effect = lambda accs: (
            call_order.append("registry")
        )

        delete_filings_batch([record], chroma=chroma, registry=registry)

        assert call_order == ["chroma", "registry"]

    def test_empty_list_short_circuits(self):
        chroma = MagicMock()
        registry = MagicMock()

        total = delete_filings_batch([], chroma=chroma, registry=registry)

        assert total == 0
        chroma.delete_filings_batch.assert_not_called()
        registry.remove_filings_batch.assert_not_called()

    def test_chromadb_error_propagates(self):
        records = [make_filing_record()]
        chroma = MagicMock()
        chroma.delete_filings_batch.side_effect = DatabaseError("fail")
        registry = MagicMock()

        with pytest.raises(DatabaseError):
            delete_filings_batch(records, chroma=chroma, registry=registry)

        # SQLite should NOT be called if ChromaDB fails.
        registry.remove_filings_batch.assert_not_called()


# -----------------------------------------------------------------------
# F14: MetadataRegistry batch methods
# -----------------------------------------------------------------------


class TestRemoveFilingsBatch:
    """remove_filings_batch() batches SQLite DELETE statements."""

    @pytest.fixture
    def registry(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return MetadataRegistry(db_path=db_path)

    def _insert_filings(self, registry, accessions):
        """Helper to insert test filings."""
        for i, acc in enumerate(accessions):
            filing_id = FilingIdentifier(
                ticker="TEST",
                form_type="10-K",
                filing_date=date(2024, 1, 1) + timedelta(days=i),
                accession_number=acc,
            )
            registry.register_filing(filing_id, chunk_count=10)

    def test_removes_multiple_filings(self, registry):
        accessions = ["ACC-001", "ACC-002", "ACC-003"]
        self._insert_filings(registry, accessions)

        removed = registry.remove_filings_batch(["ACC-001", "ACC-003"])

        assert removed == 2
        assert registry.get_filing("ACC-001") is None
        assert registry.get_filing("ACC-002") is not None
        assert registry.get_filing("ACC-003") is None

    def test_empty_list_returns_zero(self, registry):
        removed = registry.remove_filings_batch([])
        assert removed == 0

    def test_nonexistent_accessions_ignored(self, registry):
        self._insert_filings(registry, ["ACC-001"])
        removed = registry.remove_filings_batch(["ACC-001", "NONEXISTENT"])
        assert removed == 1

    def test_handles_large_batch_chunking(self, registry):
        """Batches of >999 accessions are chunked correctly."""
        # Create 1050 filings
        accessions = [f"ACC-{i:05d}" for i in range(1050)]
        self._insert_filings(registry, accessions)

        removed = registry.remove_filings_batch(accessions)
        assert removed == 1050
        assert registry.count() == 0


class TestGetFilingsByAccessions:
    """get_filings_by_accessions() batches SELECT queries."""

    @pytest.fixture
    def registry(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return MetadataRegistry(db_path=db_path)

    def _insert_filings(self, registry, accessions):
        for i, acc in enumerate(accessions):
            filing_id = FilingIdentifier(
                ticker="TEST",
                form_type="10-K",
                filing_date=date(2024, 1, 1) + timedelta(days=i),
                accession_number=acc,
            )
            registry.register_filing(filing_id, chunk_count=10)

    def test_returns_matching_records(self, registry):
        self._insert_filings(registry, ["ACC-001", "ACC-002", "ACC-003"])

        results = registry.get_filings_by_accessions(["ACC-001", "ACC-003"])

        assert len(results) == 2
        found_accessions = {r.accession_number for r in results}
        assert found_accessions == {"ACC-001", "ACC-003"}

    def test_empty_list_returns_empty(self, registry):
        results = registry.get_filings_by_accessions([])
        assert results == []

    def test_nonexistent_accessions_omitted(self, registry):
        self._insert_filings(registry, ["ACC-001"])
        results = registry.get_filings_by_accessions(
            ["ACC-001", "NONEXISTENT"],
        )
        assert len(results) == 1
        assert results[0].accession_number == "ACC-001"

    def test_handles_large_batch_chunking(self, registry):
        """Batches of >999 accessions are chunked correctly."""
        accessions = [f"ACC-{i:05d}" for i in range(1050)]
        self._insert_filings(registry, accessions)

        results = registry.get_filings_by_accessions(accessions)
        assert len(results) == 1050
