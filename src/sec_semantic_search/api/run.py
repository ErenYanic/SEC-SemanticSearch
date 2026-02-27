"""
Launch helper for the FastAPI backend.

Provides the ``main()`` entry point used by the ``sec-search-api``
console script defined in ``pyproject.toml``.

Usage::

    sec-search-api                          # default: 0.0.0.0:8000
    sec-search-api --port 8080              # custom port
    sec-search-api --reload                 # auto-reload for development
    uvicorn sec_semantic_search.api.app:app  # direct uvicorn alternative
"""

import argparse

import uvicorn


def main() -> None:
    """Launch the FastAPI app via uvicorn."""
    from sec_semantic_search.config import get_settings

    settings = get_settings()

    parser = argparse.ArgumentParser(description="SEC Semantic Search API server")
    parser.add_argument(
        "--host",
        default=settings.api.host,
        help=f"Bind host (default: {settings.api.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.api.port,
        help=f"Port number (default: {settings.api.port})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    args = parser.parse_args()

    uvicorn.run(
        "sec_semantic_search.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )