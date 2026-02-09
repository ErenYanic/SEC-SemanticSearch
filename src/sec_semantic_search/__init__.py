"""SEC-SemanticSearch — semantic search over SEC filings.

This package provides the complete pipeline for fetching, parsing, chunking,
embedding, and searching SEC filings (10-K, 10-Q).

Usage:
    from sec_semantic_search import __version__
    from sec_semantic_search.config import get_settings
    from sec_semantic_search.search import SearchEngine
    from sec_semantic_search.pipeline import PipelineOrchestrator
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sec-semantic-search")
except PackageNotFoundError:
    __version__ = "0.0.0"

# Re-export lightweight core types for convenience.
# Heavy modules (pipeline, database, search) are NOT imported here to avoid
# pulling in torch, chromadb, and sentence-transformers on every import.
from sec_semantic_search.core import (
    Chunk,
    ContentType,
    FilingIdentifier,
    IngestResult,
    SearchResult,
    SECSemanticSearchError,
    Segment,
)

__all__ = [
    "__version__",
    # Core types
    "ContentType",
    "FilingIdentifier",
    "Segment",
    "Chunk",
    "SearchResult",
    "IngestResult",
    # Base exception
    "SECSemanticSearchError",
]
