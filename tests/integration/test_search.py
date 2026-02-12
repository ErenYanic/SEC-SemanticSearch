"""Integration tests for the SearchEngine facade.

SearchEngine coordinates EmbeddingGenerator and ChromaDBClient. We use
a real ChromaDB instance (with tmp_chroma_path for isolation) but mock
the EmbeddingGenerator to avoid loading the 300M-parameter model.

The mock embedder returns deterministic fake embeddings — this lets us
test the SearchEngine's own logic (threshold filtering, parameter
defaults, error handling) without GPU overhead.

The SearchEngine constructor accepts an optional embedder via dependency
injection (architectural decision #17), which is exactly what makes
this testable without the real model.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from sec_semantic_search.config.constants import EMBEDDING_DIMENSION
from sec_semantic_search.core.exceptions import SearchError
from sec_semantic_search.database.client import ChromaDBClient
from sec_semantic_search.pipeline.orchestrator import ProcessedFiling
from sec_semantic_search.search.engine import SearchEngine


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def mock_embedder():
    """A mock EmbeddingGenerator that returns deterministic embeddings.

    embed_query_for_chromadb() returns a fixed vector wrapped in the
    list-of-lists format ChromaDB expects. This avoids loading the
    real sentence-transformer model.
    """
    embedder = MagicMock()
    rng = np.random.default_rng(42)
    fake_query_embedding = rng.random(EMBEDDING_DIMENSION, dtype=np.float32)
    embedder.embed_query_for_chromadb.return_value = [fake_query_embedding.tolist()]
    return embedder


@pytest.fixture
def populated_chroma(tmp_chroma_path, sample_chunks, sample_filing_id):
    """A ChromaDB client pre-populated with sample chunks.

    Returns the client so tests can pass it to SearchEngine.
    """
    client = ChromaDBClient(chroma_path=tmp_chroma_path)
    embeddings = np.random.default_rng(42).random(
        (len(sample_chunks), EMBEDDING_DIMENSION), dtype=np.float32
    )
    pf = ProcessedFiling(
        filing_id=sample_filing_id,
        segments=[],
        chunks=sample_chunks,
        embeddings=embeddings,
        ingest_result=None,
    )
    client.store_filing(pf)
    return client


@pytest.fixture
def engine(mock_embedder, populated_chroma):
    """SearchEngine wired with mock embedder and populated ChromaDB."""
    return SearchEngine(embedder=mock_embedder, chroma_client=populated_chroma)


# -----------------------------------------------------------------------
# Search returns results
# -----------------------------------------------------------------------


class TestSearchReturnsResults:
    """After storing chunks, search should find them."""

    def test_basic_search(self, engine):
        """A query should return at least one SearchResult."""
        results = engine.search("revenue and financial performance")
        assert len(results) > 0

    def test_result_has_metadata(self, engine):
        """Each result should carry the expected metadata fields."""
        results = engine.search("business description")
        result = results[0]
        assert result.ticker == "AAPL"
        assert result.form_type == "10-K"
        assert result.content  # Non-empty content
        assert result.path  # Non-empty path
        assert 0.0 <= result.similarity <= 1.0

    def test_results_ordered_by_similarity(self, engine):
        """Results should be in descending similarity order."""
        results = engine.search("risk factors")
        similarities = [r.similarity for r in results]
        assert similarities == sorted(similarities, reverse=True)


# -----------------------------------------------------------------------
# Input validation
# -----------------------------------------------------------------------


class TestInputValidation:
    """SearchEngine should reject invalid queries early."""

    def test_empty_query_raises(self, engine):
        with pytest.raises(SearchError, match="Empty search query"):
            engine.search("")

    def test_whitespace_query_raises(self, engine):
        with pytest.raises(SearchError, match="Empty search query"):
            engine.search("   \t\n  ")


# -----------------------------------------------------------------------
# Similarity threshold filtering
# -----------------------------------------------------------------------


class TestSimilarityFiltering:
    """min_similarity filtering is SearchEngine's unique logic."""

    def test_high_threshold_filters_all(self, engine):
        """A threshold of 1.0 should filter out everything (perfect match impossible)."""
        results = engine.search("test query", min_similarity=1.0)
        assert len(results) == 0

    def test_zero_threshold_keeps_all(self, engine):
        """A threshold of 0.0 should keep all results."""
        all_results = engine.search("test query", min_similarity=0.0)
        assert len(all_results) > 0


# -----------------------------------------------------------------------
# Filters passed to ChromaDB
# -----------------------------------------------------------------------


class TestQueryFilters:
    """Ticker and form_type filters should be forwarded to ChromaDB."""

    def test_matching_ticker_returns_results(self, engine):
        results = engine.search("test", ticker="AAPL")
        assert len(results) > 0

    def test_non_matching_ticker_returns_empty(self, engine):
        results = engine.search("test", ticker="MSFT")
        assert len(results) == 0

    def test_matching_form_type_returns_results(self, engine):
        results = engine.search("test", form_type="10-K")
        assert len(results) > 0

    def test_non_matching_form_type_returns_empty(self, engine):
        results = engine.search("test", form_type="10-Q")
        assert len(results) == 0


# -----------------------------------------------------------------------
# top_k parameter
# -----------------------------------------------------------------------


class TestTopK:
    """The top_k parameter should limit the number of results."""

    def test_top_k_limits_results(self, engine):
        results = engine.search("test", top_k=1)
        assert len(results) <= 1

    def test_top_k_larger_than_collection(self, engine):
        """Requesting more results than exist should return all available."""
        results = engine.search("test", top_k=100)
        # We stored 3 sample chunks, so we should get at most 3
        assert len(results) <= 3
