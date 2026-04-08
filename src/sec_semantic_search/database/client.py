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

        self._migrate_filing_date_int()

    # ------------------------------------------------------------------
    # Migrations
    # ------------------------------------------------------------------

    _MIGRATION_FLAG = "migration_filing_date_int_done"

    def _set_collection_flag(self, flag: str, value: bool = True) -> None:
        """Set a custom metadata flag on the collection.

        Filters out HNSW configuration keys (e.g. ``hnsw:space``)
        before calling ``modify()`` — ChromaDB rejects metadata updates
        that include distance-function settings, even if the value is
        unchanged.
        """
        current = self._collection.metadata or {}
        filtered = {k: v for k, v in current.items() if not k.startswith("hnsw:")}
        filtered[flag] = value
        self._collection.modify(metadata=filtered)

    def _migrate_filing_date_int(self) -> None:
        """
        Backfill ``filing_date_int`` for chunks ingested before BF-012.

        Scans all documents in the collection and adds the integer
        ``YYYYMMDD`` field to any chunk that has ``filing_date`` but
        is missing ``filing_date_int``.

        A metadata flag on the collection tracks whether the migration
        has already completed. Once set, subsequent startups skip the
        scan entirely — reducing startup from O(N/1000) batches to a
        single O(1) metadata check.
        """
        collection_meta = self._collection.metadata or {}
        if collection_meta.get(self._MIGRATION_FLAG):
            logger.debug("filing_date_int migration already complete — skipping")
            return

        total = self._collection.count()
        if total == 0:
            self._set_collection_flag(self._MIGRATION_FLAG)
            return

        batch_size = 1000
        migrated = 0

        for offset in range(0, total, batch_size):
            batch = self._collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas"],
            )

            ids_to_update: list[str] = []
            metas_to_update: list[dict] = []

            for doc_id, meta in zip(
                batch["ids"],
                batch["metadatas"],
                strict=True,
            ):
                if "filing_date_int" not in meta and "filing_date" in meta:
                    meta["filing_date_int"] = int(meta["filing_date"].replace("-", ""))
                    ids_to_update.append(doc_id)
                    metas_to_update.append(meta)

            if ids_to_update:
                self._collection.update(
                    ids=ids_to_update,
                    metadatas=metas_to_update,
                )
                migrated += len(ids_to_update)

        if migrated > 0:
            logger.info(
                "Migrated %d chunk(s): added filing_date_int field",
                migrated,
            )

        # Mark migration complete only after a full successful scan.
        self._set_collection_flag(self._MIGRATION_FLAG)

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
                f"Failed to batch-delete {len(accession_numbers)} filing(s) from ChromaDB",
                details=str(e),
            ) from e

    def clear_collection(self) -> int:
        """
        Delete all documents from the collection and recreate it.

        More efficient than fetching all accession numbers and calling
        ``delete_filings_batch()`` — avoids loading data into memory.
        Deletes the entire collection and recreates it with the same
        settings (cosine similarity, migration flag).

        Returns:
            Number of chunks that were in the collection before clearing.

        Raises:
            DatabaseError: If the operation fails.
        """
        try:
            count = self._collection.count()
            if count == 0:
                return 0

            self._client.delete_collection(name=COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    self._MIGRATION_FLAG: True,
                },
            )
            logger.info(
                "Cleared ChromaDB collection: %d chunk(s) removed",
                count,
            )
            return count
        except Exception as e:
            raise DatabaseError(
                "Failed to clear ChromaDB collection",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        ticker: str | list[str] | None = None,
        form_type: str | list[str] | None = None,
        accession_number: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[SearchResult]:
        """
        Query the collection for similar chunks.

        Args:
            query_embeddings: Query embedding in ChromaDB format
                (``list[list[float]]``), typically from
                ``EmbeddingGenerator.embed_query_for_chromadb()``.
            n_results: Maximum number of results to return.
            ticker: Optional filter by ticker symbol(s). A single string
                or a list of strings (matched via ``$in``).
            form_type: Optional filter by form type(s). A single string
                or a list of strings.
            accession_number: Optional filter to restrict search to
                specific filing(s) by accession number.
            start_date: Optional lower bound for filing_date (inclusive,
                ``YYYY-MM-DD``). Lexicographic comparison works because
                dates are stored in ISO 8601 format.
            end_date: Optional upper bound for filing_date (inclusive,
                ``YYYY-MM-DD``).

        Returns:
            List of SearchResult objects, ordered by similarity
            (highest first).

        Raises:
            DatabaseError: If the query fails.
        """
        where_filter = self._build_where_filter(
            ticker, form_type, accession_number, start_date, end_date
        )

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
    def _build_field_condition(field: str, value: str | list[str], upper: bool = False) -> dict:
        """
        Build a single ChromaDB field condition.

        For a single value, returns ``{"field": value}``.
        For multiple values, returns ``{"field": {"$in": values}}``.
        """
        if isinstance(value, list):
            values = [v.upper() for v in value] if upper else list(value)
            if len(values) == 1:
                return {field: values[0]}
            return {field: {"$in": values}}
        return {field: value.upper() if upper else value}

    @staticmethod
    def _date_str_to_int(date_str: str) -> int:
        """
        Convert an ISO date string to a ``YYYYMMDD`` integer.

        Args:
            date_str: Date in ``YYYY-MM-DD`` format.

        Returns:
            Integer representation, e.g. ``"2023-01-15"`` → ``20230115``.
        """
        return int(date_str.replace("-", ""))

    @staticmethod
    def _build_where_filter(
        ticker: str | list[str] | None = None,
        form_type: str | list[str] | None = None,
        accession_number: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict | None:
        """
        Build a ChromaDB where filter from optional parameters.

        ChromaDB uses ``{"field": "value"}`` for single conditions,
        ``{"field": {"$in": [...]}}`` for multi-value conditions,
        ``{"$and": [...]}`` for multiple conditions, and comparison
        operators (``$gte``, ``$lte``) for range queries.

        Date range filters use the ``filing_date_int`` field (an integer
        in ``YYYYMMDD`` format) because ChromaDB's ``$gte``/``$lte``
        operators only accept numeric operands.

        Args:
            ticker: Optional ticker filter (single or list).
            form_type: Optional form type filter (single or list).
            accession_number: Optional accession number filter
                (single or list).
            start_date: Optional lower bound for filing_date
                (inclusive, ``YYYY-MM-DD``).
            end_date: Optional upper bound for filing_date
                (inclusive, ``YYYY-MM-DD``).

        Returns:
            Where filter dict, or None if no filters specified.
        """
        conditions = []
        if ticker:
            conditions.append(ChromaDBClient._build_field_condition("ticker", ticker, upper=True))
        if form_type:
            conditions.append(
                ChromaDBClient._build_field_condition("form_type", form_type, upper=True)
            )
        if accession_number:
            conditions.append(
                ChromaDBClient._build_field_condition("accession_number", accession_number)
            )
        if start_date:
            conditions.append(
                {"filing_date_int": {"$gte": ChromaDBClient._date_str_to_int(start_date)}}
            )
        if end_date:
            conditions.append(
                {"filing_date_int": {"$lte": ChromaDBClient._date_str_to_int(end_date)}}
            )

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
