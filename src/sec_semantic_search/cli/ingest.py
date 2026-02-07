"""Ingest subcommands for adding SEC filings to the database."""

from typing import Annotated

import typer
from rich.console import Console

from sec_semantic_search.config import SUPPORTED_FORMS
from sec_semantic_search.core import (
    DatabaseError,
    FetchError,
    FilingLimitExceededError,
    SECSemanticSearchError,
)
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.pipeline import PipelineOrchestrator
from sec_semantic_search.pipeline.fetch import FilingFetcher

console = Console()

ingest_app = typer.Typer(no_args_is_help=True)


@ingest_app.command("add")
def add(
    ticker: Annotated[str, typer.Argument(help="Stock ticker symbol (e.g. AAPL).")],
    form: Annotated[
        str,
        typer.Option("--form", "-f", help="SEC form type."),
    ] = "10-K",
) -> None:
    """Fetch and ingest the latest SEC filing for a company."""
    ticker = ticker.upper()
    form = form.upper()

    if form not in SUPPORTED_FORMS:
        console.print(
            f"[red]Unsupported form type:[/red] {form}. "
            f"Supported: {', '.join(SUPPORTED_FORMS)}"
        )
        raise typer.Exit(code=1)

    registry = MetadataRegistry()
    chroma = ChromaDBClient()

    # 1. Check filing limit before doing any work.
    try:
        registry.check_filing_limit()
    except FilingLimitExceededError as e:
        console.print(f"[red]Filing limit reached:[/red] {e.message}")
        raise typer.Exit(code=1) from None

    # 2. Fetch the latest filing (cheap network call).
    with console.status(f"Fetching latest {form} for {ticker}..."):
        try:
            fetcher = FilingFetcher()
            filing_id, html_content = fetcher.fetch_latest(ticker, form)
        except FetchError as e:
            console.print(f"[red]Fetch failed:[/red] {e.message}")
            if e.details:
                console.print(f"  [dim]{e.details}[/dim]")
            raise typer.Exit(code=1) from None

    # 3. Check for duplicates before expensive processing.
    if registry.is_duplicate(filing_id.accession_number):
        console.print(
            f"[yellow]Already ingested:[/yellow] {ticker} {form} "
            f"({filing_id.date_str}, {filing_id.accession_number})"
        )
        raise typer.Exit(code=0)

    # 4. Run the pipeline (parse → chunk → embed).
    with console.status("Processing filing (parse, chunk, embed)..."):
        try:
            orchestrator = PipelineOrchestrator(fetcher=fetcher)
            result = orchestrator.process_filing(filing_id, html_content)
        except SECSemanticSearchError as e:
            console.print(f"[red]Processing failed:[/red] {e.message}")
            if e.details:
                console.print(f"  [dim]{e.details}[/dim]")
            raise typer.Exit(code=1) from None

    # 5. Store: ChromaDB first, then SQLite.
    try:
        chroma.store_filing(result)
        registry.register_filing(result.filing_id, result.ingest_result.chunk_count)
    except DatabaseError as e:
        console.print(f"[red]Storage failed:[/red] {e.message}")
        raise typer.Exit(code=1) from None

    # 6. Summary.
    stats = result.ingest_result
    console.print(
        f"[green]Ingested:[/green] {ticker} {form} ({filing_id.date_str})\n"
        f"  Segments: {stats.segment_count}  |  "
        f"Chunks: {stats.chunk_count}  |  "
        f"Time: {stats.duration_seconds:.1f}s"
    )


@ingest_app.command("batch")
def batch(
    tickers: Annotated[
        list[str],
        typer.Argument(help="Stock ticker symbols (e.g. AAPL MSFT GOOGL)."),
    ],
    form: Annotated[
        str,
        typer.Option("--form", "-f", help="SEC form type."),
    ] = "10-K",
) -> None:
    """Fetch and ingest the latest filings for multiple companies."""
    tickers = [t.upper() for t in tickers]
    form = form.upper()

    if form not in SUPPORTED_FORMS:
        console.print(
            f"[red]Unsupported form type:[/red] {form}. "
            f"Supported: {', '.join(SUPPORTED_FORMS)}"
        )
        raise typer.Exit(code=1)

    registry = MetadataRegistry()
    chroma = ChromaDBClient()

    succeeded = 0
    skipped = 0
    failed = 0

    for ticker in tickers:
        # Check filing limit before each ingestion.
        try:
            registry.check_filing_limit()
        except FilingLimitExceededError as e:
            console.print(f"[red]Filing limit reached:[/red] {e.message}")
            console.print("[dim]Stopping batch ingestion.[/dim]")
            break

        console.print(f"\n[bold]{ticker}[/bold] {form}")

        # Fetch.
        with console.status(f"  Fetching latest {form} for {ticker}..."):
            try:
                fetcher = FilingFetcher()
                filing_id, html_content = fetcher.fetch_latest(ticker, form)
            except FetchError as e:
                console.print(f"  [red]Fetch failed:[/red] {e.message}")
                failed += 1
                continue

        # Duplicate check.
        if registry.is_duplicate(filing_id.accession_number):
            console.print(
                f"  [yellow]Already ingested:[/yellow] "
                f"{filing_id.date_str} ({filing_id.accession_number})"
            )
            skipped += 1
            continue

        # Process.
        with console.status("  Processing filing (parse, chunk, embed)..."):
            try:
                orchestrator = PipelineOrchestrator(fetcher=fetcher)
                result = orchestrator.process_filing(filing_id, html_content)
            except SECSemanticSearchError as e:
                console.print(f"  [red]Processing failed:[/red] {e.message}")
                failed += 1
                continue

        # Store.
        try:
            chroma.store_filing(result)
            registry.register_filing(result.filing_id, result.ingest_result.chunk_count)
        except DatabaseError as e:
            console.print(f"  [red]Storage failed:[/red] {e.message}")
            failed += 1
            continue

        stats = result.ingest_result
        console.print(
            f"  [green]Ingested:[/green] {filing_id.date_str}  |  "
            f"Chunks: {stats.chunk_count}  |  "
            f"Time: {stats.duration_seconds:.1f}s"
        )
        succeeded += 1

    # Summary.
    console.print(
        f"\n[bold]Batch complete:[/bold] "
        f"[green]{succeeded} ingested[/green], "
        f"[yellow]{skipped} skipped[/yellow], "
        f"[red]{failed} failed[/red]"
    )
