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

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from sec_semantic_search import __version__
from sec_semantic_search.api.dependencies import verify_api_key
from sec_semantic_search.api.rate_limit import RateLimitMiddleware
from sec_semantic_search.config import get_settings
from sec_semantic_search.core import get_logger

logger = get_logger(__name__)

_CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data: https:",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com",
    "connect-src 'self' ws: wss:",
])


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), interest-cohort=()"
        )
        return response


class InsecureTransportWarningMiddleware(BaseHTTPMiddleware):
    """Log a one-time warning when protected traffic arrives over HTTP."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._warned = False

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        if not self._warned:
            self._maybe_warn(request)
        return await call_next(request)

    def _maybe_warn(self, request: Request) -> None:
        settings = get_settings()
        if not (
            settings.api.key
            or settings.api.admin_key
            or settings.api.edgar_session_required
        ):
            return

        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto is None:
            return

        proto = forwarded_proto.split(",", 1)[0].strip().lower()
        if proto != "http":
            return

        self._warned = True
        logger.warning(
            "Insecure transport detected (X-Forwarded-Proto=http) while "
            "authentication or per-session EDGAR credentials are enabled. "
            "Scenarios B and C require TLS; enable HTTPS at the reverse proxy "
            "or launch the API with --ssl-certfile/--ssl-keyfile.",
        )


# ---------------------------------------------------------------------------
# Request body size limit middleware
# ---------------------------------------------------------------------------

# 1 MB — matches nginx client_max_body_size; defence in depth for
# direct-to-uvicorn access (local dev without reverse proxy).
_MAX_CONTENT_LENGTH = 1 * 1024 * 1024


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose ``Content-Length`` exceeds the allowed limit.

    This is a lightweight, header-based check.  It does not consume the
    body — it simply inspects the ``Content-Length`` header and returns
    413 if the declared size is too large.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header."},
                )
            if length > _MAX_CONTENT_LENGTH:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": {
                            "error": "payload_too_large",
                            "message": (
                                f"Request body too large ({length:,} bytes). "
                                f"Maximum allowed: {_MAX_CONTENT_LENGTH:,} bytes."
                            ),
                            "details": None,
                            "hint": "Reduce the request payload size.",
                        },
                    },
                )
        return await call_next(request)


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
        6. PipelineOrchestrator (wraps fetcher + embedder — fast)
        7. TaskManager (wraps registry + chroma + fetcher + orchestrator)
    """
    from sec_semantic_search.api.tasks import TaskManager
    from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
    from sec_semantic_search.pipeline import (
        EmbeddingGenerator,
        FilingFetcher,
        PipelineOrchestrator,
    )
    from sec_semantic_search.search import SearchEngine

    logger.info("SEC Semantic Search API starting up (v%s)", __version__)

    settings = get_settings()

    registry = MetadataRegistry()
    chroma = ChromaDBClient()
    embedder = EmbeddingGenerator()
    search_engine = SearchEngine(embedder=embedder, chroma_client=chroma)
    fetcher = FilingFetcher()
    orchestrator = PipelineOrchestrator(fetcher=fetcher, embedder=embedder)
    task_manager = TaskManager(
        registry=registry,
        chroma=chroma,
        fetcher=fetcher,
        orchestrator=orchestrator,
    )

    # Give the TaskManager a reference to the running event loop so
    # worker threads can bridge messages into the asyncio.Queue via
    # call_soon_threadsafe.
    task_manager.set_event_loop(asyncio.get_running_loop())

    app.state.registry = registry
    app.state.chroma = chroma
    app.state.embedder = embedder
    app.state.search_engine = search_engine
    app.state.fetcher = fetcher
    app.state.orchestrator = orchestrator
    app.state.task_manager = task_manager
    app.state.settings = settings

    logger.info("All singletons initialised. API ready.")
    yield
    logger.info("SEC Semantic Search API shutting down.")
    task_manager.shutdown()
    registry.close()


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

    # Disable OpenAPI/Swagger UI when authentication is enabled (Scenarios
    # B/C).  In dev mode (no API_KEY) the docs remain available for API
    # discoverability.  See SECURITY VULNERABILITIES.md §F1.
    is_protected = bool(settings.api.key)

    application = FastAPI(
        title="SEC Semantic Search API",
        description=(
            "REST API for semantic search over ingested SEC filings "
            "(8-K, 10-K, 10-Q). Wraps the sec-semantic-search Python package "
            "over HTTP."
        ),
        version=__version__,
        docs_url=None if is_protected else "/docs",
        redoc_url=None if is_protected else "/redoc",
        openapi_url=None if is_protected else "/openapi.json",
        lifespan=lifespan,
    )

    # -- Request body size limit --------------------------------------------
    application.add_middleware(ContentSizeLimitMiddleware)

    # -- Rate limiting ------------------------------------------------------
    application.add_middleware(
        RateLimitMiddleware,
        search_rpm=settings.api.rate_limit_search,
        ingest_rpm=settings.api.rate_limit_ingest,
        delete_rpm=settings.api.rate_limit_delete,
        general_rpm=settings.api.rate_limit_general,
    )

    # -- Security headers ---------------------------------------------------
    application.add_middleware(SecurityHeadersMiddleware)

    # -- Transport security warning -----------------------------------------
    application.add_middleware(InsecureTransportWarningMiddleware)

    # -- CORS ---------------------------------------------------------------
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Admin-Key",
            "X-Edgar-Name",
            "X-Edgar-Email",
        ],
    )

    # -- Routers (uncommented as implemented in W1.2–W1.8) ------------------
    from sec_semantic_search.api.routes.filings import router as filings_router
    from sec_semantic_search.api.routes.ingest import router as ingest_router
    from sec_semantic_search.api.routes.resources import router as resources_router
    from sec_semantic_search.api.routes.search import router as search_router
    from sec_semantic_search.api.routes.status import router as status_router
    from sec_semantic_search.api.websocket import router as ws_router

    auth = [Depends(verify_api_key)]
    application.include_router(status_router, prefix="/api/status", tags=["status"], dependencies=auth)
    application.include_router(filings_router, prefix="/api/filings", tags=["filings"], dependencies=auth)
    application.include_router(search_router, prefix="/api/search", tags=["search"], dependencies=auth)
    application.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"], dependencies=auth)
    application.include_router(ws_router, tags=["websocket"])  # WS validates key in handler
    application.include_router(resources_router, prefix="/api/resources", tags=["resources"], dependencies=auth)

    # -- Health check -------------------------------------------------------
    @application.get("/api/health", tags=["meta"], summary="Health check")
    async def health() -> dict[str, str]:
        """Return API liveness status.

        The version is intentionally omitted from this unauthenticated
        endpoint to avoid disclosing it to anonymous clients (see
        SECURITY VULNERABILITIES.md §F3).  Authenticated users can
        obtain the version via ``GET /api/status/``.
        """
        return {"status": "ok"}

    return application


app = create_app()
