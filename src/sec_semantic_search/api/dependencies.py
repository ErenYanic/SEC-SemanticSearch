"""
FastAPI dependency providers for SEC-SemanticSearch.

All dependencies read pre-initialised singletons from ``request.app.state``
(set during the lifespan startup in ``app.py``).  This guarantees that
route handlers share a single ChromaDB connection, a single SQLite
registry, and a single embedding model instance across the process.

Usage in route modules::

    from fastapi import Depends
    from sec_semantic_search.api.dependencies import get_registry

    @router.get("/")
    async def list_filings(
        registry: MetadataRegistry = Depends(get_registry),
    ):
        return registry.list_filings()
"""

from fastapi import Request

from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.pipeline import EmbeddingGenerator, FilingFetcher
from sec_semantic_search.search import SearchEngine


def get_registry(request: Request) -> MetadataRegistry:
    """Provide the MetadataRegistry singleton."""
    registry: MetadataRegistry = request.app.state.registry
    return registry


def get_chroma(request: Request) -> ChromaDBClient:
    """Provide the ChromaDBClient singleton."""
    chroma: ChromaDBClient = request.app.state.chroma
    return chroma


def get_search_engine(request: Request) -> SearchEngine:
    """Provide the SearchEngine singleton."""
    engine: SearchEngine = request.app.state.search_engine
    return engine


def get_fetcher(request: Request) -> FilingFetcher:
    """Provide the FilingFetcher singleton."""
    fetcher: FilingFetcher = request.app.state.fetcher
    return fetcher


def get_embedder(request: Request) -> EmbeddingGenerator:
    """Provide the EmbeddingGenerator singleton."""
    embedder: EmbeddingGenerator = request.app.state.embedder
    return embedder