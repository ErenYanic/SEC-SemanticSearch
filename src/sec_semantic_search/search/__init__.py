"""Search module — semantic search over ingested SEC filings.

This module provides the high-level search interface:
    - SearchEngine: Facade coordinating query embedding and similarity search

Usage:
    from sec_semantic_search.search import SearchEngine

    engine = SearchEngine()
    results = engine.search("revenue and financial performance")
"""

from sec_semantic_search.search.engine import SearchEngine

__all__ = [
    "SearchEngine",
]
