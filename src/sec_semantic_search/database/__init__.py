"""Database module — ChromaDB vector storage and SQLite metadata registry.

This module provides the storage layer for ingested SEC filings:
    - ChromaDBClient: Vector storage for chunk embeddings and similarity search
    - MetadataRegistry: SQLite registry for filing metadata and management
    - FilingRecord: Dataclass representing a filing registry entry

Usage:
    from sec_semantic_search.database import (
        ChromaDBClient,
        MetadataRegistry,
    )

    # Store a processed filing
    client = ChromaDBClient()
    registry = MetadataRegistry()

    registry.check_filing_limit()
    client.store_filing(processed_filing)
    registry.register_filing(processed_filing.filing_id, chunk_count=59)
"""

from sec_semantic_search.database.client import ChromaDBClient
from sec_semantic_search.database.metadata import FilingRecord, MetadataRegistry

__all__ = [
    # Main classes
    "ChromaDBClient",
    "MetadataRegistry",
    # Supporting types
    "FilingRecord",
]
