"""
Unit tests for the clear_all optimisation (F-OPT-05).

Verifies:
    - ``MetadataRegistry.clear_all()`` deletes all rows efficiently.
    - ``ChromaDBClient.clear_collection()`` deletes and recreates.
    - ``clear_all_filings()`` orchestrates both stores.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.core.types import FilingIdentifier
from sec_semantic_search.database import clear_all_filings
from sec_semantic_search.database.metadata import MetadataRegistry


# ── MetadataRegistry.clear_all() ────────────────────────────────────


@pytest.fixture
def registry(tmp_db_path) -> MetadataRegistry:
    return MetadataRegistry(db_path=tmp_db_path)


@pytest.fixture
def sample_ids() -> list[FilingIdentifier]:
    """Three distinct filing identifiers."""
    return [
        FilingIdentifier(
            ticker="AAPL", form_type="10-K",
            filing_date=date(2023, 1, 15),
            accession_number="0000320193-23-000077",
        ),
        FilingIdentifier(
            ticker="MSFT", form_type="10-Q",
            filing_date=date(2023, 3, 20),
            accession_number="0000789019-23-000010",
        ),
        FilingIdentifier(
            ticker="GOOGL", form_type="10-K",
            filing_date=date(2023, 6, 30),
            accession_number="0001652044-23-000099",
        ),
    ]


class TestMetadataRegistryClearAll:
    """MetadataRegistry.clear_all() deletes all rows efficiently."""

    def test_clear_empty_returns_zero(self, registry):
        assert registry.clear_all() == 0

    def test_clear_returns_count(self, registry, sample_ids):
        for fid in sample_ids:
            registry.register_filing(fid, chunk_count=10)
        assert registry.count() == 3

        removed = registry.clear_all()
        assert removed == 3
        assert registry.count() == 0

    def test_clear_idempotent(self, registry, sample_ids):
        for fid in sample_ids:
            registry.register_filing(fid, chunk_count=10)

        registry.clear_all()
        assert registry.clear_all() == 0

    def test_clear_does_not_affect_task_history(self, registry, sample_ids):
        """clear_all only removes filings, not task_history rows."""
        for fid in sample_ids:
            registry.register_filing(fid, chunk_count=10)

        registry.save_task_history(
            "task-1",
            status="completed",
            tickers=["AAPL"],
            form_types=["10-K"],
            results=[],
        )

        registry.clear_all()
        assert registry.count() == 0
        assert registry.get_task_history("task-1") is not None


# ── ChromaDBClient.clear_collection() ───────────────────────────────


class TestChromaDBClearCollection:
    """ChromaDBClient.clear_collection() deletes and recreates."""

    def test_clear_empty_returns_zero(self):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.metadata = {"hnsw:space": "cosine"}

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_settings = MagicMock()
        mock_settings.database.chroma_path = "/tmp/test"

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_client
            from sec_semantic_search.database.client import ChromaDBClient
            client = ChromaDBClient(chroma_path="/tmp/test")

            result = client.clear_collection()

        assert result == 0
        mock_client.delete_collection.assert_not_called()

    def test_clear_nonempty_returns_count(self):
        from sec_semantic_search.database.client import ChromaDBClient

        mock_collection = MagicMock()
        mock_collection.count.return_value = 500
        mock_collection.metadata = {
            "hnsw:space": "cosine",
            ChromaDBClient._MIGRATION_FLAG: True,
        }

        new_collection = MagicMock()

        mock_client = MagicMock()
        mock_client.get_or_create_collection.side_effect = [
            mock_collection,  # __init__
            new_collection,   # clear_collection recreate
        ]

        mock_settings = MagicMock()
        mock_settings.database.chroma_path = "/tmp/test"

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_client
            client = ChromaDBClient(chroma_path="/tmp/test")
            result = client.clear_collection()

        assert result == 500
        mock_client.delete_collection.assert_called_once_with(name="sec_filings")

    def test_clear_recreates_with_migration_flag(self):
        from sec_semantic_search.database.client import ChromaDBClient

        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.metadata = {
            "hnsw:space": "cosine",
            ChromaDBClient._MIGRATION_FLAG: True,
        }

        new_collection = MagicMock()

        mock_client = MagicMock()
        mock_client.get_or_create_collection.side_effect = [
            mock_collection,
            new_collection,
        ]

        mock_settings = MagicMock()
        mock_settings.database.chroma_path = "/tmp/test"

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_client
            client = ChromaDBClient(chroma_path="/tmp/test")
            client.clear_collection()

        # Verify the recreated collection has cosine + migration flag
        create_call = mock_client.get_or_create_collection.call_args_list[-1]
        metadata = create_call[1]["metadata"]
        assert metadata["hnsw:space"] == "cosine"
        assert metadata[ChromaDBClient._MIGRATION_FLAG] is True


# ── clear_all_filings() orchestration ───────────────────────────────


class TestClearAllFilings:
    """clear_all_filings() orchestrates both stores."""

    def test_returns_counts(self):
        mock_chroma = MagicMock()
        mock_chroma.clear_collection.return_value = 1500

        mock_registry = MagicMock()
        mock_registry.clear_all.return_value = 30

        filings_deleted, chunks_deleted = clear_all_filings(
            chroma=mock_chroma, registry=mock_registry,
        )

        assert filings_deleted == 30
        assert chunks_deleted == 1500

    def test_chromadb_called_before_sqlite(self):
        call_order = []

        mock_chroma = MagicMock()
        mock_chroma.clear_collection.side_effect = lambda: (call_order.append("chroma"), 0)[1]

        mock_registry = MagicMock()
        mock_registry.clear_all.side_effect = lambda: (call_order.append("sqlite"), 0)[1]

        clear_all_filings(chroma=mock_chroma, registry=mock_registry)

        assert call_order == ["chroma", "sqlite"]
