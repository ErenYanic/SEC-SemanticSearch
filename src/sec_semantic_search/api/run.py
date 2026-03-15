"""
Launch helper for the FastAPI backend.

Provides the ``main()`` entry point used by the ``sec-search-api``
console script defined in ``pyproject.toml``.

Usage::

    sec-search-api                          # default: 127.0.0.1:8000
    sec-search-api --port 8080              # custom port
    sec-search-api --reload                 # auto-reload for development
    uvicorn sec_semantic_search.api.app:app  # direct uvicorn alternative

For HTTPS (simple deployments without a reverse proxy)::

    sec-search-api --ssl-certfile cert.pem --ssl-keyfile key.pem

For production deployments, use a reverse proxy (nginx, Caddy) with TLS
termination in front of the API.  See the README for details.
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
    parser.add_argument(
        "--ssl-certfile",
        default=None,
        help="Path to SSL certificate file for HTTPS",
    )
    parser.add_argument(
        "--ssl-keyfile",
        default=None,
        help="Path to SSL private key file for HTTPS",
    )
    args = parser.parse_args()

    uvicorn_kwargs: dict = {
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
    }
    if args.ssl_certfile and args.ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = args.ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = args.ssl_keyfile

    uvicorn.run("sec_semantic_search.api.app:app", **uvicorn_kwargs)