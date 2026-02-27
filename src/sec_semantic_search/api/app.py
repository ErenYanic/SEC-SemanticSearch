"""
FastAPI application factory for SEC-SemanticSearch.

The public symbol is ``app`` — the ASGI application object used by
uvicorn and by the test client.

Architecture:
    - Singletons (ChromaDBClient, MetadataRegistry, SearchEngine,
      FilingFetcher) are initialised once in the lifespan context
      manager and stored on ``app.state``.
    - Route modules access them through dependency functions in
      ``dependencies.py`` (which read from ``request.app.state``).
    - No business logic lives here — this is pure wiring.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sec_semantic_search import __version__
from sec_semantic_search.config import get_settings
from sec_semantic_search.core import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — initialise singletons, store on app.state
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Initialise and clean up application-level singletons.

    Heavy imports happen here (not at module top level) to keep
    ``import sec_semantic_search.api.app`` lightweight and avoid
    pulling torch/chromadb at test collection time.

    Startup order:
        1. MetadataRegistry (SQLite — fast)
        2. ChromaDBClient (ChromaDB — fast; model not loaded yet)
        3. EmbeddingGenerator (lazy — model loads on first use)
        4. SearchEngine (wraps embedder + chroma — fast)
        5. FilingFetcher (sets EDGAR identity — fast)
    """
    from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
    from sec_semantic_search.pipeline import EmbeddingGenerator, FilingFetcher
    from sec_semantic_search.search import SearchEngine

    logger.info("SEC Semantic Search API starting up (v%s)", __version__)

    settings = get_settings()

    registry = MetadataRegistry()
    chroma = ChromaDBClient()
    embedder = EmbeddingGenerator()
    search_engine = SearchEngine(embedder=embedder, chroma_client=chroma)
    fetcher = FilingFetcher()

    app.state.registry = registry
    app.state.chroma = chroma
    app.state.embedder = embedder
    app.state.search_engine = search_engine
    app.state.fetcher = fetcher
    app.state.settings = settings

    logger.info("All singletons initialised. API ready.")
    yield
    logger.info("SEC Semantic Search API shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns a fully configured ASGI application with CORS middleware,
    lifespan management, and a health-check endpoint. Route modules
    are included as they are implemented in W1.2–W1.8.
    """
    settings = get_settings()

    application = FastAPI(
        title="SEC Semantic Search API",
        description=(
            "REST API for semantic search over ingested SEC filings "
            "(10-K, 10-Q). Wraps the sec-semantic-search Python package "
            "over HTTP."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # -- CORS ---------------------------------------------------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Routers (uncommented as implemented in W1.2–W1.8) ------------------
    from sec_semantic_search.api.routes.filings import router as filings_router
    from sec_semantic_search.api.routes.status import router as status_router
    # from sec_semantic_search.api.routes.search import router as search_router
    # from sec_semantic_search.api.routes.ingest import router as ingest_router
    # from sec_semantic_search.api.routes.resources import router as resources_router

    application.include_router(status_router, prefix="/api/status", tags=["status"])
    application.include_router(filings_router, prefix="/api/filings", tags=["filings"])
    # application.include_router(search_router, prefix="/api/search", tags=["search"])
    # application.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
    # application.include_router(resources_router, prefix="/api/resources", tags=["resources"])

    # -- Health check -------------------------------------------------------
    @application.get("/api/health", tags=["meta"], summary="Health check")
    async def health() -> dict[str, str]:
        """Return API liveness status."""
        return {"status": "ok", "version": __version__}

    return application


app = create_app()