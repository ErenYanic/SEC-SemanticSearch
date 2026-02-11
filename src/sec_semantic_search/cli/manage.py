"""Database management subcommands (status, list, remove)."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sec_semantic_search.config import get_settings
from sec_semantic_search.core import DatabaseError
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry

console = Console()

manage_app = typer.Typer(no_args_is_help=True)


@manage_app.command("status")
def status() -> None:
    """Show database status and filing statistics."""
    registry = MetadataRegistry()
    chroma = ChromaDBClient()
    settings = get_settings()

    filing_count = registry.count()
    chunk_count = chroma.collection_count()
    max_filings = settings.database.max_filings
    filings = registry.list_filings()

    # Build a key-value table for the status metrics.
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    # Filings count with capacity indicator.
    filing_style = "green" if filing_count > 0 else "dim"
    table.add_row("Filings", Text(f"{filing_count}/{max_filings}", style=filing_style))

    # Chunk count.
    chunk_style = "green" if chunk_count > 0 else "dim"
    table.add_row("Chunks", Text(str(chunk_count), style=chunk_style))

    if filings:
        # Compute per-form-type breakdown.
        unique_tickers: set[str] = set()
        form_counts: dict[str, int] = {}
        for f in filings:
            unique_tickers.add(f.ticker)
            form_counts[f.form_type] = form_counts.get(f.form_type, 0) + 1

        ticker_list = ", ".join(sorted(unique_tickers))
        table.add_row(
            "Tickers",
            Text(f"{len(unique_tickers)} ({ticker_list})", style="cyan"),
        )

        breakdown = "  |  ".join(
            f"{form}: {count}" for form, count in sorted(form_counts.items())
        )
        table.add_row("Forms", Text(breakdown))
    else:
        table.add_row("Tickers", Text("—", style="dim"))
        table.add_row("Forms", Text("—", style="dim"))

    console.print(Panel(table, title="[bold]Database Status[/bold]", expand=False))


@manage_app.command("list")
def list_filings(
    ticker: Annotated[
        Optional[str],
        typer.Option("--ticker", "-k", help="Filter by ticker symbol."),
    ] = None,
    form: Annotated[
        Optional[str],
        typer.Option("--form", "-f", help="Filter by form type."),
    ] = None,
) -> None:
    """List all ingested filings."""
    registry = MetadataRegistry()
    filings = registry.list_filings(
        ticker=ticker.upper() if ticker else None,
        form_type=form.upper() if form else None,
    )

    if not filings:
        console.print("[yellow]No filings found.[/yellow]")
        return

    table = Table(
        title="[bold]Ingested Filings[/bold]",
        border_style="dim",
        header_style="bold",
    )
    table.add_column("Ticker", style="cyan")
    table.add_column("Form", style="green")
    table.add_column("Filing Date")
    table.add_column("Accession Number", style="dim")
    table.add_column("Chunks", justify="right", style="bold")
    table.add_column("Ingested At", style="dim")

    for f in filings:
        table.add_row(
            f.ticker,
            f.form_type,
            f.filing_date,
            f.accession_number,
            str(f.chunk_count),
            f.ingested_at,
        )

    console.print(table)


@manage_app.command("remove")
def remove(
    accession_number: Annotated[
        str,
        typer.Argument(help="Accession number of the filing to remove."),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove a filing from the database."""
    registry = MetadataRegistry()

    # Show filing details before confirming deletion.
    filing = registry.get_filing(accession_number)
    if filing is None:
        console.print(f"[red]Filing not found:[/red] {accession_number}")
        console.print(
            "  [dim italic]Hint: Run 'sec-search manage list' to see available "
            "accession numbers.[/dim italic]"
        )
        raise typer.Exit(code=1)

    detail = Table(show_header=False, box=None, padding=(0, 2))
    detail.add_column("Key", style="bold")
    detail.add_column("Value")
    detail.add_row("Filing", Text(f"{filing.ticker} {filing.form_type}", style="cyan"))
    detail.add_row("Date", Text(filing.filing_date))
    detail.add_row("Chunks", Text(str(filing.chunk_count), style="bold"))
    detail.add_row("Accession", Text(filing.accession_number, style="dim"))
    console.print(Panel(detail, title="[bold yellow]Remove Filing[/bold yellow]", expand=False))

    if not yes:
        confirmed = typer.confirm("Remove this filing?")
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(code=0)

    # Delete: ChromaDB first, then SQLite.
    try:
        chroma = ChromaDBClient()
        chunks_deleted = chroma.delete_filing(accession_number)
        registry.remove_filing(accession_number)
    except DatabaseError as e:
        console.print(f"[red]Removal failed:[/red] {e.message}")
        console.print(
            "  [dim italic]Hint: Check that the data directory is writable.[/dim italic]"
        )
        raise typer.Exit(code=1) from None

    console.print(
        f"[green]Removed:[/green] {filing.ticker} {filing.form_type} "
        f"({filing.filing_date}) — {chunks_deleted} chunks deleted"
    )
