"""Typer application root for the sec-search CLI."""

import logging
from importlib.metadata import version

import typer
from rich.console import Console

from sec_semantic_search.cli.ingest import ingest_app
from sec_semantic_search.cli.manage import manage_app
from sec_semantic_search.cli.search import search
from sec_semantic_search.core.logging import configure_logging, suppress_third_party_loggers

# Shared console instance for consistent output across all CLI modules.
console = Console()

app = typer.Typer(
    name="sec-search",
    help="Semantic search for SEC filings (10-K, 10-Q).",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"sec-search {version('sec-semantic-search')}")
        raise typer.Exit()


def _verbose_callback(value: bool) -> None:
    """Enable DEBUG-level logging when --verbose is passed."""
    if value:
        configure_logging(level=logging.DEBUG)
        suppress_third_party_loggers()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    _verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable detailed debug output.",
        callback=_verbose_callback,
        is_eager=True,
    ),
) -> None:
    """Semantic search for SEC filings (10-K, 10-Q)."""


# Register sub-command groups.
app.add_typer(ingest_app, name="ingest", help="Ingest SEC filings into the database.")
app.add_typer(manage_app, name="manage", help="Manage the filing database.")

# Register search as a top-level command (not a sub-group).
app.command(name="search")(search)
