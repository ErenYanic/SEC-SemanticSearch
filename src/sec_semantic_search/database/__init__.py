"""
Database module — ChromaDB vector storage and SQLite metadata registry.

This module provides the storage layer for ingested SEC filings:
    - ChromaDBClient: Vector storage for chunk embeddings and similarity search
    - MetadataRegistry: SQLite registry for filing metadata and management
    - FilingRecord: Dataclass representing a filing registry entry
    - delete_filings_batch: Shared helper to delete filings from both stores

Usage:
    from sec_semantic_search.database import (
        ChromaDBClient,
        MetadataRegistry,
        delete_filings_batch,
    )

    # Store a processed filing
    client = ChromaDBClient()
    registry = MetadataRegistry()

    registry.check_filing_limit()
    client.store_filing(processed_filing)
    registry.register_filing(processed_filing.filing_id, chunk_count=59)

    # Delete filings from both stores
    filings = registry.list_filings(ticker="AAPL")
    total_chunks = delete_filings_batch(filings, chroma=client, registry=registry)
"""

from sec_semantic_search.core import get_logger
from sec_semantic_search.database.client import ChromaDBClient
from sec_semantic_search.database.metadata import (
    DatabaseStatistics,
    FilingRecord,
    MetadataRegistry,
    TickerStatistics,
)

logger = get_logger(__name__)


def delete_filings_batch(
    filings: list[FilingRecord],
    *,
    chroma: ChromaDBClient,
    registry: MetadataRegistry,
) -> int:
    """
    Delete a list of filings from both stores (ChromaDB first, then SQLite).

    This is the single source of truth for dual-store deletion logic,
    used by both the CLI and API layers.

    Args:
        filings: Filing records to delete.
        chroma: ChromaDB client instance.
        registry: Metadata registry instance.

    Returns:
        Total number of chunks deleted across all filings.

    Raises:
        DatabaseError: If any individual deletion fails (propagated
            from ChromaDBClient or MetadataRegistry).
    """
    total_chunks = 0
    for filing in filings:
        chroma.delete_filing(filing.accession_number)
        registry.remove_filing(filing.accession_number)
        total_chunks += filing.chunk_count
        logger.info(
            "Deleted %s %s (%s) — %d chunks",
            filing.ticker,
            filing.form_type,
            filing.filing_date,
            filing.chunk_count,
        )
    return total_chunks


__all__ = [
    # Main classes
    "ChromaDBClient",
    "MetadataRegistry",
    # Supporting types
    "DatabaseStatistics",
    "FilingRecord",
    "TickerStatistics",
    # Helpers
    "delete_filings_batch",
]
