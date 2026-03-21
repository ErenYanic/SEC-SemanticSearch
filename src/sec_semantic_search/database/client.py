"""
ChromaDB client wrapper for vector storage operations.

This module manages a single ChromaDB collection (``sec_filings``) that stores
chunk embeddings with metadata for similarity search. It handles storage,
deletion, and querying of vector data.

Usage:
    from sec_semantic_search.database import ChromaDBClient

    client = ChromaDBClient()
    client.store_filing(processed_filing)
    results = client.query(query_embeddings, n_results=5)
"""


import chromadb

from sec_semantic_search.config import get_settings
from sec_semantic_search.config.constants import COLLECTION_NAME
from sec_semantic_search.core import DatabaseError, SearchResult, get_logger
from sec_semantic_search.pipeline import ProcessedFiling

logger = get_logger(__name__)


class ChromaDBClient:
    """
    Wrapper around ChromaDB for SEC filing vector storage.

    This class manages a single collection (``sec_filings``) that stores
    all filing chunks with their embeddings and metadata. It uses cosine
    similarity for distance calculation.

    The ChromaDB ``PersistentClient`` handles disk persistence automatically.
    Data is written to disk on every add/delete operation.

    Example:
        >>> client = ChromaDBClient()
        >>> client.store_filing(processed_filing)
        >>> results = client.query(query_embeddings, n_results=5)
    """

    def __init__(self, chroma_path: str | None = None) -> None:
        """
        Initialise the ChromaDB client and collection.

        Creates a persistent client and gets or creates the unified
        ``sec_filings`` collection with cosine similarity.

        Args:
            chroma_path: Path to ChromaDB storage directory. If None,
                         uses ``settings.database.chroma_path``.
        """
        settings = get_settings()
        self._chroma_path = chroma_path or settings.database.chroma_path

        try:
            self._client = chromadb.PersistentClient(
                path=self._chroma_path,
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.debug(
                "ChromaDBClient initialised: %s (collection: %s, count: %d)",
                self._chroma_path,
                COLLECTION_NAME,
                self._collection.count(),
            )
        except Exception as e:
            raise DatabaseError(
                "Failed to initialise ChromaDB",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def store_filing(self, processed_filing: ProcessedFiling) -> None:
        """
        Store all chunks and embeddings from a processed filing.

        Adds the chunks, their embeddings, text content, and metadata to
        the ChromaDB collection in a single batch operation.

        Args:
            processed_filing: Output from ``PipelineOrchestrator`` containing
                              chunks, embeddings, and filing metadata.

        Raises:
            DatabaseError: If the storage operation fails.
        """
        chunks = processed_filing.chunks
        embeddings = processed_filing.embeddings
        filing_id = processed_filing.filing_id

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.to_metadata() for chunk in chunks]

        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info(
                "Stored %d chunks for %s %s (%s)",
                len(chunks),
                filing_id.ticker,
                filing_id.form_type,
                filing_id.date_str,
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to store filing {filing_id.accession_number}",
                details=str(e),
            ) from e

    def delete_filing(self, accession_number: str) -> None:
        """
        Delete all chunks belonging to a filing.

        Uses a single ``delete(where=...)`` call to remove all chunks
        matching the accession number, avoiding the extra round-trip of
        querying for IDs first.

        Callers that need the deleted chunk count should read
        ``FilingRecord.chunk_count`` from the SQLite registry before
        calling this method.

        Args:
            accession_number: SEC accession number of the filing to remove.

        Raises:
            DatabaseError: If the deletion fails.
        """
        try:
            self._collection.delete(
                where={"accession_number": accession_number},
            )
            logger.info(
                "Deleted chunks from ChromaDB for accession: %s",
                accession_number,
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to delete filing {accession_number} from ChromaDB",
                details=str(e),
            ) from e

    def delete_filings_batch(self, accession_numbers: list[str]) -> None:
        """
        Delete all chunks belonging to multiple filings in one call.

        Uses ChromaDB's ``$in`` operator to match all accession numbers
        in a single ``delete(where=...)`` call, reducing round-trips
        from O(N) to O(1).

        Args:
            accession_numbers: Accession numbers whose chunks to remove.

        Raises:
            DatabaseError: If the deletion fails.
        """
        if not accession_numbers:
            return

        try:
            self._collection.delete(
                where={
                    "accession_number": {"$in": accession_numbers},
                },
            )
            logger.info(
                "Batch-deleted chunks from ChromaDB for %d filing(s)",
                len(accession_numbers),
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to batch-delete {len(accession_numbers)} "
                f"filing(s) from ChromaDB",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        ticker: str | None = None,
        form_type: str | None = None,
        accession_number: str | None = None,
    ) -> list[SearchResult]:
        """
        Query the collection for similar chunks.

        Args:
            query_embeddings: Query embedding in ChromaDB format
                (``list[list[float]]``), typically from
                ``EmbeddingGenerator.embed_query_for_chromadb()``.
            n_results: Maximum number of results to return.
            ticker: Optional filter by ticker symbol.
            form_type: Optional filter by form type.
            accession_number: Optional filter to restrict search to a
                single filing (web-only feature).

        Returns:
            List of SearchResult objects, ordered by similarity
            (highest first).

        Raises:
            DatabaseError: If the query fails.
        """
        where_filter = self._build_where_filter(ticker, form_type, accession_number)

        try:
            results = self._collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            search_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    search_results.append(
                        SearchResult.from_chromadb_result(
                            document=results["documents"][0][i],
                            metadata=results["metadatas"][0][i],
                            distance=results["distances"][0][i],
                            chunk_id=results["ids"][0][i],
                        )
                    )

            logger.debug("Query returned %d results", len(search_results))
            return search_results

        except Exception as e:
            raise DatabaseError(
                "ChromaDB query failed",
                details=str(e),
            ) from e

    def collection_count(self) -> int:
        """
        Return the total number of chunks in the collection.

        Returns:
            Number of documents in the ChromaDB collection.
        """
        return self._collection.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where_filter(
        ticker: str | None = None,
        form_type: str | None = None,
        accession_number: str | None = None,
    ) -> dict | None:
        """
        Build a ChromaDB where filter from optional parameters.

        ChromaDB uses ``{"field": "value"}`` for single conditions and
        ``{"$and": [...]}`` for multiple conditions.

        Args:
            ticker: Optional ticker filter.
            form_type: Optional form type filter.
            accession_number: Optional accession number filter
                (restricts search to a single filing).

        Returns:
            Where filter dict, or None if no filters specified.
        """
        conditions = []
        if ticker:
            conditions.append({"ticker": ticker.upper()})
        if form_type:
            conditions.append({"form_type": form_type.upper()})
        if accession_number:
            conditions.append({"accession_number": accession_number})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
