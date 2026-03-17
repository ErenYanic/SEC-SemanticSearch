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

from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# EDGAR session credentials
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgarIdentity:
    """EDGAR identity resolved from request headers or server-side env vars."""

    name: str
    email: str


async def get_edgar_identity(request: Request) -> EdgarIdentity:
    """Resolve EDGAR identity from request headers or server-side env vars.

    Resolution order:
        1. ``X-Edgar-Name`` / ``X-Edgar-Email`` request headers (per-session)
        2. Server-side ``EDGAR_IDENTITY_NAME`` / ``EDGAR_IDENTITY_EMAIL`` env vars
        3. 401 if neither is available and ``EDGAR_SESSION_REQUIRED`` is true

    EDGAR credentials are **never logged** — not even at DEBUG level.
    """
    settings = get_settings()

    # 1. Try request headers (per-session credentials from frontend).
    header_name = request.headers.get("X-Edgar-Name")
    header_email = request.headers.get("X-Edgar-Email")
    if header_name and header_email:
        return EdgarIdentity(name=header_name.strip(), email=header_email.strip())

    # 2. Fall back to server-side env vars.
    env_name = settings.edgar.identity_name
    env_email = settings.edgar.identity_email
    if env_name and env_email:
        return EdgarIdentity(name=env_name, email=env_email)

    # 3. Neither available — reject if session credentials are required.
    if settings.api.edgar_session_required:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "edgar_credentials_required",
                "message": "EDGAR credentials are required for ingestion.",
                "details": None,
                "hint": (
                    "Provide X-Edgar-Name and X-Edgar-Email headers, or "
                    "configure EDGAR_IDENTITY_NAME and EDGAR_IDENTITY_EMAIL "
                    "server-side."
                ),
            },
        )

    # Session not required and no server-side env vars — allow without
    # credentials (Scenario A with partial config).  The EDGAR library
    # itself will raise if identity is truly needed.
    raise HTTPException(
        status_code=401,
        detail={
            "error": "edgar_credentials_missing",
            "message": "No EDGAR credentials available.",
            "details": None,
            "hint": (
                "Set EDGAR_IDENTITY_NAME and EDGAR_IDENTITY_EMAIL in .env, "
                "or provide X-Edgar-Name and X-Edgar-Email headers."
            ),
        },
    )