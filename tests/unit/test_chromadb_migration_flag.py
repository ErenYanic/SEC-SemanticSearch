"""
Unit tests for ChromaDB migration flag (F-OPT-02).

Verifies that the ``_migrate_filing_date_int`` migration:
    - Sets a metadata flag on the collection after the first run.
    - Skips the full scan on subsequent initialisations (O(1) check).
    - Marks empty collections as migrated immediately.
"""

from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.database.client import ChromaDBClient


@pytest.fixture
def mock_settings():
    """Provide a minimal settings mock for ChromaDBClient."""
    settings = MagicMock()
    settings.database.chroma_path = "/tmp/test_chroma"
    return settings


@pytest.fixture
def mock_collection():
    """Provide a mock ChromaDB collection with controllable metadata."""
    collection = MagicMock()
    collection.metadata = {"hnsw:space": "cosine"}
    collection.count.return_value = 0
    return collection


@pytest.fixture
def mock_chroma_client(mock_collection):
    """Provide a mock ChromaDB PersistentClient."""
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


class TestMigrationFlagEmptyCollection:
    """Empty collections are flagged as migrated immediately."""

    def test_empty_collection_sets_flag(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        mock_collection.count.return_value = 0

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        mock_collection.modify.assert_called_once()
        call_kwargs = mock_collection.modify.call_args[1]
        assert call_kwargs["metadata"][ChromaDBClient._MIGRATION_FLAG] is True


class TestMigrationFlagSkipsWhenDone:
    """Subsequent startups skip the migration scan."""

    def test_skips_scan_when_flag_set(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        mock_collection.metadata = {
            "hnsw:space": "cosine",
            ChromaDBClient._MIGRATION_FLAG: True,
        }
        mock_collection.count.return_value = 100

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        # Should NOT call .get() (the scan) or .modify() (setting flag)
        mock_collection.get.assert_not_called()
        mock_collection.modify.assert_not_called()

    def test_does_not_scan_when_flag_true(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        """Even with many chunks, the scan is skipped when flagged."""
        mock_collection.metadata = {
            "hnsw:space": "cosine",
            ChromaDBClient._MIGRATION_FLAG: True,
        }
        mock_collection.count.return_value = 50_000

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        mock_collection.get.assert_not_called()


class TestMigrationFlagSetAfterScan:
    """The flag is set after a successful migration scan."""

    def test_flag_set_after_migrating_chunks(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        mock_collection.count.return_value = 2
        mock_collection.get.return_value = {
            "ids": ["chunk_1", "chunk_2"],
            "metadatas": [
                {"filing_date": "2023-01-15"},
                {"filing_date": "2023-06-30", "filing_date_int": 20230630},
            ],
        }

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        # Should have updated the chunk missing filing_date_int
        mock_collection.update.assert_called_once()
        update_ids = mock_collection.update.call_args[1]["ids"]
        assert "chunk_1" in update_ids

        # Should have set the migration flag
        mock_collection.modify.assert_called_once()
        call_kwargs = mock_collection.modify.call_args[1]
        assert call_kwargs["metadata"][ChromaDBClient._MIGRATION_FLAG] is True

    def test_flag_set_even_when_no_chunks_need_migration(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        """All chunks already have filing_date_int — flag still gets set."""
        mock_collection.count.return_value = 1
        mock_collection.get.return_value = {
            "ids": ["chunk_1"],
            "metadatas": [
                {"filing_date": "2023-01-15", "filing_date_int": 20230115},
            ],
        }

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        # No update needed, but flag should still be set
        mock_collection.update.assert_not_called()
        mock_collection.modify.assert_called_once()
        call_kwargs = mock_collection.modify.call_args[1]
        assert call_kwargs["metadata"][ChromaDBClient._MIGRATION_FLAG] is True


class TestMigrationFlagNoneMetadata:
    """Handle collections with None metadata gracefully."""

    def test_none_metadata_does_not_crash(
        self, mock_settings, mock_chroma_client, mock_collection,
    ):
        mock_collection.metadata = None
        mock_collection.count.return_value = 0

        with (
            patch("sec_semantic_search.database.client.get_settings", return_value=mock_settings),
            patch("sec_semantic_search.database.client.chromadb") as mock_chromadb,
        ):
            mock_chromadb.PersistentClient.return_value = mock_chroma_client
            mock_chroma_client.get_or_create_collection.return_value = mock_collection

            ChromaDBClient(chroma_path="/tmp/test")

        mock_collection.modify.assert_called_once()
        call_kwargs = mock_collection.modify.call_args[1]
        assert call_kwargs["metadata"][ChromaDBClient._MIGRATION_FLAG] is True
