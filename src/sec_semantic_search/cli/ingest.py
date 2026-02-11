"""Ingest subcommands for adding SEC filings to the database."""

from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

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

# Step labels used in the progress display for ingestion.
_STEPS = ["Fetching", "Parsing", "Chunking", "Embedding", "Storing"]


def _print_error(
    label: str,
    message: str,
    *,
    details: str | None = None,
    hint: str | None = None,
) -> None:
    """Print a consistently formatted error with optional details and hint."""
    console.print(f"[red]{label}:[/red] {message}")
    if details:
        console.print(f"  [dim]{details}[/dim]")
    if hint:
        console.print(f"  [dim italic]Hint: {hint}[/dim italic]")


def _make_progress() -> Progress:
    """Create a Rich Progress instance for ingestion steps."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("{task.completed}/{task.total} steps"),
        TimeElapsedColumn(),
        console=console,
    )


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
        _print_error(
            "Filing limit reached",
            e.message,
            hint="Remove filings with 'sec-search manage remove' or raise the limit via DB_MAX_FILINGS.",
        )
        raise typer.Exit(code=1) from None

    with _make_progress() as progress:
        task = progress.add_task(f"Fetching {ticker} {form}...", total=len(_STEPS))

        # 2. Fetch the latest filing (cheap network call).
        try:
            fetcher = FilingFetcher()
            filing_id, html_content = fetcher.fetch_latest(ticker, form)
        except FetchError as e:
            progress.stop()
            _print_error(
                "Fetch failed",
                e.message,
                details=e.details,
                hint="Check the ticker symbol is valid and you have an internet connection.",
            )
            raise typer.Exit(code=1) from None

        progress.advance(task)

        # 3. Check for duplicates before expensive processing.
        if registry.is_duplicate(filing_id.accession_number):
            progress.stop()
            console.print(
                f"[yellow]Already ingested:[/yellow] {ticker} {form} "
                f"({filing_id.date_str}, {filing_id.accession_number})"
            )
            raise typer.Exit(code=0)

        # 4. Run the pipeline (parse → chunk → embed).
        #    The orchestrator callback drives steps 2-4 of the progress bar.
        def _on_progress(step: str, _current: int, _total: int) -> None:
            if step != "Complete":
                progress.update(task, description=f"{step}...")
                progress.advance(task)

        try:
            orchestrator = PipelineOrchestrator(fetcher=fetcher)
            result = orchestrator.process_filing(
                filing_id, html_content, progress_callback=_on_progress
            )
        except SECSemanticSearchError as e:
            progress.stop()
            _print_error(
                "Processing failed",
                e.message,
                details=e.details,
                hint="If this is a memory error, try lowering EMBEDDING_BATCH_SIZE in .env.",
            )
            raise typer.Exit(code=1) from None

        # 5. Store: ChromaDB first, then SQLite.
        progress.update(task, description="Storing...")
        try:
            chroma.store_filing(result)
            registry.register_filing(
                result.filing_id, result.ingest_result.chunk_count
            )
        except DatabaseError as e:
            progress.stop()
            _print_error(
                "Storage failed",
                e.message,
                hint="Check disk space and that the data directory is writable.",
            )
            raise typer.Exit(code=1) from None

        progress.advance(task)

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

    with _make_progress() as progress:
        overall = progress.add_task(
            f"Batch: 0/{len(tickers)} tickers", total=len(tickers)
        )
        step_task = progress.add_task("Waiting...", total=len(_STEPS), visible=False)

        for i, ticker in enumerate(tickers):
            # Check filing limit before each ingestion.
            try:
                registry.check_filing_limit()
            except FilingLimitExceededError as e:
                progress.stop()
                _print_error(
                    "Filing limit reached",
                    e.message,
                    hint="Remove filings with 'sec-search manage remove' or raise the limit via DB_MAX_FILINGS.",
                )
                break

            progress.update(
                overall, description=f"Batch: {i + 1}/{len(tickers)} — {ticker}"
            )
            progress.update(
                step_task,
                description=f"Fetching {ticker}...",
                completed=0,
                visible=True,
            )

            # Fetch.
            try:
                fetcher = FilingFetcher()
                filing_id, html_content = fetcher.fetch_latest(ticker, form)
            except FetchError as e:
                progress.console.print(f"  [red]{ticker}: Fetch failed —[/red] {e.message}")
                failed += 1
                progress.advance(overall)
                continue

            progress.advance(step_task)

            # Duplicate check.
            if registry.is_duplicate(filing_id.accession_number):
                progress.console.print(
                    f"  [yellow]{ticker}: Already ingested[/yellow] "
                    f"({filing_id.date_str})"
                )
                skipped += 1
                progress.advance(overall)
                continue

            # Process — wire orchestrator callback to progress bar.
            def _on_progress(step: str, _current: int, _total: int) -> None:
                if step != "Complete":
                    progress.update(step_task, description=f"{step} {ticker}...")
                    progress.advance(step_task)

            try:
                orchestrator = PipelineOrchestrator(fetcher=fetcher)
                result = orchestrator.process_filing(
                    filing_id, html_content, progress_callback=_on_progress
                )
            except SECSemanticSearchError as e:
                progress.console.print(
                    f"  [red]{ticker}: Processing failed —[/red] {e.message}"
                )
                failed += 1
                progress.advance(overall)
                continue

            # Store.
            progress.update(step_task, description=f"Storing {ticker}...")
            try:
                chroma.store_filing(result)
                registry.register_filing(
                    result.filing_id, result.ingest_result.chunk_count
                )
            except DatabaseError as e:
                progress.console.print(
                    f"  [red]{ticker}: Storage failed —[/red] {e.message}"
                )
                failed += 1
                progress.advance(overall)
                continue

            progress.advance(step_task)

            stats = result.ingest_result
            progress.console.print(
                f"  [green]{ticker}:[/green] {filing_id.date_str}  |  "
                f"Chunks: {stats.chunk_count}  |  "
                f"Time: {stats.duration_seconds:.1f}s"
            )
            succeeded += 1
            progress.advance(overall)

        # Hide the per-filing step bar at the end.
        progress.update(step_task, visible=False)

    # Summary.
    console.print(
        f"\n[bold]Batch complete:[/bold] "
        f"[green]{succeeded} ingested[/green], "
        f"[yellow]{skipped} skipped[/yellow], "
        f"[red]{failed} failed[/red]"
    )
