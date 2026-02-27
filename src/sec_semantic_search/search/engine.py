"""
Search engine for semantic search over SEC filings.

This module provides the high-level search interface that coordinates
query embedding and ChromaDB similarity search. It serves as the
primary entry point for the CLI and any future web interface.

Usage:
    from sec_semantic_search.search import SearchEngine

    engine = SearchEngine()
    results = engine.search("revenue and financial performance")
"""

from typing import Optional

from sec_semantic_search.config import get_settings
from sec_semantic_search.core import SearchError, SearchResult, get_logger
from sec_semantic_search.database import ChromaDBClient
from sec_semantic_search.pipeline import EmbeddingGenerator

logger = get_logger(__name__)


class SearchEngine:
    """
    Facade for semantic search over ingested SEC filings.

    This class coordinates query embedding and vector similarity search,
    providing a single ``search()`` method that accepts a plain text query
    and returns ranked results. It reads defaults from ``SearchSettings``
    (``SEARCH_TOP_K``, ``SEARCH_MIN_SIMILARITY``) so callers can search
    with minimal arguments.

    The engine accepts optional pre-built dependencies so that the CLI
    layer can share an ``EmbeddingGenerator`` instance between ingestion
    and search (avoiding loading the model twice).

    Example:
        >>> engine = SearchEngine()
        >>> results = engine.search("risk factors related to supply chain")
        >>> for r in results:
        ...     print(f"[{r.similarity:.3f}] {r.path}")
    """

    def __init__(
        self,
        embedder: Optional[EmbeddingGenerator] = None,
        chroma_client: Optional[ChromaDBClient] = None,
    ) -> None:
        """
        Initialise the search engine.

        Args:
            embedder: Pre-built embedding generator. If None, a new
                      instance is created (model loads lazily on first query).
            chroma_client: Pre-built ChromaDB client. If None, a new
                           instance is created using settings.
        """
        self._embedder = embedder or EmbeddingGenerator()
        self._chroma_client = chroma_client or ChromaDBClient()

        settings = get_settings()
        self._default_top_k = settings.search.top_k
        self._default_min_similarity = settings.search.min_similarity

        logger.debug(
            "SearchEngine initialised: top_k=%d, min_similarity=%.2f",
            self._default_top_k,
            self._default_min_similarity,
        )

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        ticker: Optional[str] = None,
        form_type: Optional[str] = None,
        min_similarity: Optional[float] = None,
        accession_number: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Search ingested filings for chunks relevant to the query.

        The query is embedded using the same model used during ingestion,
        then matched against stored chunks via cosine similarity. Results
        below ``min_similarity`` are filtered out.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return. Defaults to
                   ``SEARCH_TOP_K`` from settings.
            ticker: Optional filter — only search filings from this ticker.
            form_type: Optional filter — only search this form type
                       (e.g. "10-K", "10-Q").
            min_similarity: Minimum similarity threshold (0.0–1.0).
                            Defaults to ``SEARCH_MIN_SIMILARITY`` from settings.
            accession_number: Optional filter — restrict search to a single
                filing by accession number (web-only feature).

        Returns:
            List of ``SearchResult`` objects ordered by similarity
            (highest first), filtered by the minimum similarity threshold.

        Raises:
            SearchError: If the query is empty or the search operation fails.
        """
        if not query or not query.strip():
            raise SearchError(
                "Empty search query",
                details="Cannot search with an empty or whitespace-only query.",
            )

        effective_top_k = top_k if top_k is not None else self._default_top_k
        effective_min_sim = (
            min_similarity if min_similarity is not None else self._default_min_similarity
        )

        logger.info(
            "Searching: '%s' (top_k=%d, min_similarity=%.2f, ticker=%s, form_type=%s)",
            query[:80],
            effective_top_k,
            effective_min_sim,
            ticker or "any",
            form_type or "any",
        )

        try:
            query_embeddings = self._embedder.embed_query_for_chromadb(query)

            results = self._chroma_client.query(
                query_embeddings=query_embeddings,
                n_results=effective_top_k,
                ticker=ticker,
                form_type=form_type,
                accession_number=accession_number,
            )
        except SearchError:
            raise
        except Exception as e:
            raise SearchError(
                "Search failed",
                details=str(e),
            ) from e

        # Filter by minimum similarity threshold
        if effective_min_sim > 0.0:
            before_count = len(results)
            results = [r for r in results if r.similarity >= effective_min_sim]
            filtered_count = before_count - len(results)
            if filtered_count > 0:
                logger.debug(
                    "Filtered %d results below similarity threshold %.2f",
                    filtered_count,
                    effective_min_sim,
                )

        logger.info("Search returned %d results", len(results))
        return results
