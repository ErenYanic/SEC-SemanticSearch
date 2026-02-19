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

from sec_semantic_search.config import DEFAULT_FORM_TYPES, parse_form_types
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


def _ingest_one_form(
    ticker: str,
    form_type: str,
    *,
    registry: MetadataRegistry,
    chroma: ChromaDBClient,
    progress: Progress,
    task_id: int,
    form_label: str = "",
) -> str:
    """Ingest the latest filing for one ticker and one form type.

    Runs the full 5-step pipeline: fetch → duplicate check → process → store.

    Args:
        ticker: Uppercased stock ticker symbol.
        form_type: Single validated form type (e.g. "10-K").
        registry: MetadataRegistry instance.
        chroma: ChromaDBClient instance.
        progress: Active Rich Progress instance.
        task_id: Progress task ID for the 5-step bar.
        form_label: Optional suffix for progress descriptions (e.g. " (1/2)").

    Returns:
        "succeeded", "skipped", or "failed".
    """
    # 1. Fetch the latest filing (cheap network call).
    progress.update(task_id, description=f"Fetching {ticker} {form_type}{form_label}...")
    try:
        fetcher = FilingFetcher()
        filing_id, html_content = fetcher.fetch_latest(ticker, form_type)
    except FetchError as e:
        progress.stop()
        _print_error(
            "Fetch failed",
            e.message,
            details=e.details,
            hint="Check the ticker symbol is valid and you have an internet connection.",
        )
        return "failed"

    progress.advance(task_id)

    # 2. Check for duplicates before expensive processing.
    if registry.is_duplicate(filing_id.accession_number):
        progress.stop()
        console.print(
            f"[yellow]Already ingested:[/yellow] {ticker} {form_type} "
            f"({filing_id.date_str}, {filing_id.accession_number})"
        )
        return "skipped"

    # 3. Run the pipeline (parse → chunk → embed).
    def _on_progress(step: str, _current: int, _total: int) -> None:
        if step != "Complete":
            progress.update(task_id, description=f"{step}{form_label}...")
            progress.advance(task_id)

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
        return "failed"

    # 4. Store: ChromaDB first, then SQLite.
    progress.update(task_id, description=f"Storing{form_label}...")
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
        return "failed"

    progress.advance(task_id)

    # 5. Summary for this filing.
    stats = result.ingest_result
    progress.stop()
    console.print(
        f"[green]Ingested:[/green] {ticker} {form_type} ({filing_id.date_str})\n"
        f"  Segments: {stats.segment_count}  |  "
        f"Chunks: {stats.chunk_count}  |  "
        f"Time: {stats.duration_seconds:.1f}s"
    )
    return "succeeded"


@ingest_app.command("add")
def add(
    ticker: Annotated[str, typer.Argument(help="Stock ticker symbol (e.g. AAPL).")],
    form: Annotated[
        str,
        typer.Option(
            "--form", "-f",
            help="SEC form type(s), comma-separated (e.g. 10-K, 10-Q, or 10-K,10-Q).",
        ),
    ] = DEFAULT_FORM_TYPES,
) -> None:
    """Fetch and ingest the latest SEC filing(s) for a company."""
    ticker = ticker.upper()

    try:
        form_types = parse_form_types(form)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    registry = MetadataRegistry()
    chroma = ChromaDBClient()

    succeeded = 0
    skipped = 0
    failed = 0

    for idx, form_type in enumerate(form_types):
        # Check filing limit before each form type.
        try:
            registry.check_filing_limit()
        except FilingLimitExceededError as e:
            _print_error(
                "Filing limit reached",
                e.message,
                hint="Remove filings with 'sec-search manage remove' or raise the limit via DB_MAX_FILINGS.",
            )
            raise typer.Exit(code=1) from None

        form_label = f" ({idx + 1}/{len(form_types)})" if len(form_types) > 1 else ""

        with _make_progress() as progress:
            task = progress.add_task(
                f"Fetching {ticker} {form_type}{form_label}...",
                total=len(_STEPS),
            )
            outcome = _ingest_one_form(
                ticker,
                form_type,
                registry=registry,
                chroma=chroma,
                progress=progress,
                task_id=task,
                form_label=form_label,
            )

        if outcome == "succeeded":
            succeeded += 1
        elif outcome == "skipped":
            skipped += 1
        else:
            failed += 1

    # Show a combined summary only when multiple form types were requested.
    if len(form_types) > 1:
        console.print(
            f"\n[bold]Summary:[/bold] "
            f"[green]{succeeded} ingested[/green], "
            f"[yellow]{skipped} skipped[/yellow], "
            f"[red]{failed} failed[/red]"
        )

    if failed > 0 and succeeded == 0 and skipped == 0:
        raise typer.Exit(code=1)


@ingest_app.command("batch")
def batch(
    tickers: Annotated[
        list[str],
        typer.Argument(help="Stock ticker symbols (e.g. AAPL MSFT GOOGL)."),
    ],
    form: Annotated[
        str,
        typer.Option(
            "--form", "-f",
            help="SEC form type(s), comma-separated (e.g. 10-K, 10-Q, or 10-K,10-Q).",
        ),
    ] = DEFAULT_FORM_TYPES,
) -> None:
    """Fetch and ingest the latest filings for multiple companies."""
    tickers = [t.upper() for t in tickers]

    try:
        form_types = parse_form_types(form)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    registry = MetadataRegistry()
    chroma = ChromaDBClient()

    # Build a flat work list of (ticker, form_type) pairs.
    work_items = [(t, f) for t in tickers for f in form_types]

    succeeded = 0
    skipped = 0
    failed = 0

    with _make_progress() as progress:
        overall = progress.add_task(
            f"Batch: 0/{len(work_items)}", total=len(work_items)
        )
        step_task = progress.add_task("Waiting...", total=len(_STEPS), visible=False)

        for i, (ticker, form_type) in enumerate(work_items):
            label = f"{ticker} {form_type}"

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
                overall, description=f"Batch: {i + 1}/{len(work_items)} — {label}"
            )
            progress.update(
                step_task,
                description=f"Fetching {label}...",
                completed=0,
                visible=True,
            )

            # Fetch.
            try:
                fetcher = FilingFetcher()
                filing_id, html_content = fetcher.fetch_latest(ticker, form_type)
            except FetchError as e:
                progress.console.print(f"  [red]{label}: Fetch failed —[/red] {e.message}")
                failed += 1
                progress.advance(overall)
                continue

            progress.advance(step_task)

            # Duplicate check.
            if registry.is_duplicate(filing_id.accession_number):
                progress.console.print(
                    f"  [yellow]{label}: Already ingested[/yellow] "
                    f"({filing_id.date_str})"
                )
                skipped += 1
                progress.advance(overall)
                continue

            # Process — wire orchestrator callback to progress bar.
            def _on_progress(step: str, _current: int, _total: int) -> None:
                if step != "Complete":
                    progress.update(step_task, description=f"{step} {label}...")
                    progress.advance(step_task)

            try:
                orchestrator = PipelineOrchestrator(fetcher=fetcher)
                result = orchestrator.process_filing(
                    filing_id, html_content, progress_callback=_on_progress
                )
            except SECSemanticSearchError as e:
                progress.console.print(
                    f"  [red]{label}: Processing failed —[/red] {e.message}"
                )
                failed += 1
                progress.advance(overall)
                continue

            # Store.
            progress.update(step_task, description=f"Storing {label}...")
            try:
                chroma.store_filing(result)
                registry.register_filing(
                    result.filing_id, result.ingest_result.chunk_count
                )
            except DatabaseError as e:
                progress.console.print(
                    f"  [red]{label}: Storage failed —[/red] {e.message}"
                )
                failed += 1
                progress.advance(overall)
                continue

            progress.advance(step_task)

            stats = result.ingest_result
            progress.console.print(
                f"  [green]{label}:[/green] {filing_id.date_str}  |  "
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
