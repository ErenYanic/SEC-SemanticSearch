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

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from sec_semantic_search.config import get_settings
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.pipeline import EmbeddingGenerator, FilingFetcher
from sec_semantic_search.search import SearchEngine

# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Validate the ``X-API-Key`` header when authentication is enabled.

    If ``API_KEY`` is not configured (``None``), authentication is
    disabled and all requests are allowed.  This keeps local development
    frictionless while requiring a key in deployed environments.
    """
    expected = get_settings().api.key
    if expected is None:
        # Auth disabled — allow all requests.
        return
    if api_key is None or api_key != expected:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorised",
                "message": "Invalid or missing API key.",
                "hint": "Provide a valid key via the X-API-Key header.",
            },
        )


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


def get_task_manager(request: Request):  # noqa: ANN201
    """Provide the TaskManager singleton."""
    from sec_semantic_search.api.tasks import TaskManager

    manager: TaskManager = request.app.state.task_manager
    return manager