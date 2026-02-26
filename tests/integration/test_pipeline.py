"""
Integration tests for the ingestion pipeline and database layer.

These tests verify that modules compose correctly:
    - Parser output feeds into the chunker
    - Chunker output feeds into the database
    - MetadataRegistry CRUD operations work end-to-end
    - ChromaDB stores and retrieves chunks with correct metadata
    - Dual-store (ChromaDB + SQLite) operations stay consistent

The embedding step is skipped — loading the 300M-parameter model
takes ~10 seconds and requires CUDA. We use random numpy arrays of
the correct dimension (768) instead. The model itself is a third-party
dependency; what we verify here is that *our wiring* is correct.
"""

import numpy as np
import pytest

from sec_semantic_search.config.constants import EMBEDDING_DIMENSION
from sec_semantic_search.core.exceptions import (
    DatabaseError,
    FilingLimitExceededError,
)
from sec_semantic_search.database.client import ChromaDBClient
from sec_semantic_search.database.metadata import MetadataRegistry
from sec_semantic_search.pipeline.chunk import TextChunker
from sec_semantic_search.pipeline.orchestrator import ProcessedFiling
from sec_semantic_search.pipeline.parse import FilingParser


# -----------------------------------------------------------------------
# Parse → Chunk pipeline
# -----------------------------------------------------------------------


class TestParseChunkPipeline:
    """Verify that parser output is valid chunker input."""

    def test_parse_then_chunk(self, sample_html, sample_filing_id):
        """HTML → Parser → Chunker should produce chunks with metadata."""
        parser = FilingParser()
        chunker = TextChunker(token_limit=500, tolerance=50)

        segments = parser.parse(sample_html, sample_filing_id)
        chunks = chunker.chunk_segments(segments)

        assert len(chunks) > 0
        # Every chunk should have a valid chunk_id
        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.filing_id is sample_filing_id

    def test_sequential_indices_across_segments(self, sample_html, sample_filing_id):
        """Chunk indices should be sequential starting from 0."""
        parser = FilingParser()
        chunker = TextChunker(token_limit=500, tolerance=50)

        segments = parser.parse(sample_html, sample_filing_id)
        chunks = chunker.chunk_segments(segments)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# -----------------------------------------------------------------------
# MetadataRegistry (SQLite)
# -----------------------------------------------------------------------


class TestMetadataRegistry:
    """CRUD operations on the SQLite metadata registry."""

    def test_register_and_retrieve(self, tmp_db_path, sample_filing_id):
        """Register a filing, then retrieve it by accession number."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=10)

        record = registry.get_filing(sample_filing_id.accession_number)
        assert record is not None
        assert record.ticker == "AAPL"
        assert record.form_type == "10-K"
        assert record.chunk_count == 10

    def test_count(self, tmp_db_path, sample_filing_id):
        """count() should reflect the number of registered filings."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        assert registry.count() == 0

        registry.register_filing(sample_filing_id, chunk_count=5)
        assert registry.count() == 1

    def test_count_with_filters(self, tmp_db_path, sample_filing_id):
        """count(ticker=...) should filter correctly."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=5)

        assert registry.count(ticker="AAPL") == 1
        assert registry.count(ticker="MSFT") == 0
        assert registry.count(form_type="10-K") == 1
        assert registry.count(form_type="10-Q") == 0

    def test_list_filings(self, tmp_db_path, sample_filing_id):
        """list_filings() should return FilingRecord objects."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=10)

        filings = registry.list_filings()
        assert len(filings) == 1
        assert filings[0].accession_number == sample_filing_id.accession_number

    def test_list_filings_with_filter(self, tmp_db_path, sample_filing_id):
        """Filtering by non-matching ticker should return empty list."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=10)

        assert registry.list_filings(ticker="MSFT") == []

    def test_is_duplicate(self, tmp_db_path, sample_filing_id):
        """is_duplicate() should detect already-registered filings."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        assert registry.is_duplicate(sample_filing_id.accession_number) is False

        registry.register_filing(sample_filing_id, chunk_count=5)
        assert registry.is_duplicate(sample_filing_id.accession_number) is True

    def test_remove_filing(self, tmp_db_path, sample_filing_id):
        """remove_filing() should delete and return True; second call returns False."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=5)

        assert registry.remove_filing(sample_filing_id.accession_number) is True
        assert registry.count() == 0
        assert registry.remove_filing(sample_filing_id.accession_number) is False

    def test_duplicate_registration_raises(self, tmp_db_path, sample_filing_id):
        """Registering the same filing twice should raise DatabaseError."""
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry.register_filing(sample_filing_id, chunk_count=5)

        with pytest.raises(DatabaseError, match="already exists"):
            registry.register_filing(sample_filing_id, chunk_count=5)

    def test_filing_limit(self, tmp_db_path, sample_filing_id):
        """
        check_filing_limit() should raise when limit is reached.

        We create a registry and manually set _max_filings=1, then
        register one filing to trigger the limit.
        """
        registry = MetadataRegistry(db_path=tmp_db_path)
        registry._max_filings = 1

        registry.register_filing(sample_filing_id, chunk_count=5)

        with pytest.raises(FilingLimitExceededError):
            registry.check_filing_limit()


# -----------------------------------------------------------------------
# ChromaDBClient
# -----------------------------------------------------------------------


def _make_processed_filing(chunks, filing_id):
    """Helper: create a ProcessedFiling with random embeddings."""
    embeddings = np.random.default_rng(42).random(
        (len(chunks), EMBEDDING_DIMENSION), dtype=np.float32
    )
    return ProcessedFiling(
        filing_id=filing_id,
        segments=[],  # Not needed for storage
        chunks=chunks,
        embeddings=embeddings,
        ingest_result=None,  # Not needed for storage
    )


class TestChromaDBClient:
    """ChromaDB store, query, and delete operations."""

    def test_store_and_count(self, tmp_chroma_path, sample_chunks, sample_filing_id):
        """Storing a filing should increase the collection count."""
        client = ChromaDBClient(chroma_path=tmp_chroma_path)
        assert client.collection_count() == 0

        pf = _make_processed_filing(sample_chunks, sample_filing_id)
        client.store_filing(pf)
        assert client.collection_count() == len(sample_chunks)

    def test_query_returns_results(self, tmp_chroma_path, sample_chunks, sample_filing_id):
        """After storing chunks, querying should return SearchResult objects."""
        client = ChromaDBClient(chroma_path=tmp_chroma_path)
        pf = _make_processed_filing(sample_chunks, sample_filing_id)
        client.store_filing(pf)

        # Query with a random embedding (results won't be semantically
        # meaningful, but we verify the query pipeline works)
        query_emb = np.random.default_rng(99).random(
            (1, EMBEDDING_DIMENSION), dtype=np.float32
        ).tolist()
        results = client.query(query_emb, n_results=2)

        assert len(results) > 0
        assert results[0].ticker == "AAPL"
        assert results[0].form_type == "10-K"

    def test_query_with_ticker_filter(self, tmp_chroma_path, sample_chunks, sample_filing_id):
        """Filtering by a non-matching ticker should return no results."""
        client = ChromaDBClient(chroma_path=tmp_chroma_path)
        pf = _make_processed_filing(sample_chunks, sample_filing_id)
        client.store_filing(pf)

        query_emb = np.random.default_rng(99).random(
            (1, EMBEDDING_DIMENSION), dtype=np.float32
        ).tolist()
        results = client.query(query_emb, n_results=5, ticker="MSFT")
        assert len(results) == 0

    def test_delete_filing(self, tmp_chroma_path, sample_chunks, sample_filing_id):
        """Deleting a filing should remove all its chunks."""
        client = ChromaDBClient(chroma_path=tmp_chroma_path)
        pf = _make_processed_filing(sample_chunks, sample_filing_id)
        client.store_filing(pf)

        deleted = client.delete_filing(sample_filing_id.accession_number)
        assert deleted == len(sample_chunks)
        assert client.collection_count() == 0

    def test_delete_nonexistent_filing(self, tmp_chroma_path):
        """Deleting a non-existent filing should return 0."""
        client = ChromaDBClient(chroma_path=tmp_chroma_path)
        deleted = client.delete_filing("NONEXISTENT-ACC")
        assert deleted == 0


# -----------------------------------------------------------------------
# Dual-store consistency
# -----------------------------------------------------------------------


class TestDualStoreConsistency:
    """ChromaDB + SQLite should stay in sync during store/delete."""

    def test_store_both_delete_both(
        self,
        tmp_chroma_path,
        tmp_db_path,
        sample_chunks,
        sample_filing_id,
    ):
        """Full lifecycle: store in both → verify → delete from both → verify empty."""
        chroma = ChromaDBClient(chroma_path=tmp_chroma_path)
        registry = MetadataRegistry(db_path=tmp_db_path)

        # Store (ChromaDB first, then SQLite — matches production order)
        pf = _make_processed_filing(sample_chunks, sample_filing_id)
        chroma.store_filing(pf)
        registry.register_filing(sample_filing_id, chunk_count=len(sample_chunks))

        # Verify both populated
        assert chroma.collection_count() == len(sample_chunks)
        assert registry.count() == 1

        # Delete (ChromaDB first, then SQLite — matches production order)
        chroma.delete_filing(sample_filing_id.accession_number)
        registry.remove_filing(sample_filing_id.accession_number)

        # Verify both empty
        assert chroma.collection_count() == 0
        assert registry.count() == 0
