"""Database management subcommands (status, list, remove)."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from sec_semantic_search.core import DatabaseError
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry

console = Console()

manage_app = typer.Typer(no_args_is_help=True)


@manage_app.command("status")
def status() -> None:
    """Show database status and filing statistics."""
    registry = MetadataRegistry()
    chroma = ChromaDBClient()

    filing_count = registry.count()
    chunk_count = chroma.collection_count()
    filings = registry.list_filings()

    console.print(f"\n[bold]Database Status[/bold]\n")
    console.print(f"  Filings:  {filing_count}")
    console.print(f"  Chunks:   {chunk_count}")

    if not filings:
        console.print("\n  [dim]No filings ingested yet.[/dim]")
        return

    # Compute per-form-type breakdown.
    unique_tickers = set()
    form_counts: dict[str, int] = {}
    for f in filings:
        unique_tickers.add(f.ticker)
        form_counts[f.form_type] = form_counts.get(f.form_type, 0) + 1

    console.print(f"  Tickers:  {len(unique_tickers)} ({', '.join(sorted(unique_tickers))})")

    if form_counts:
        breakdown = "  |  ".join(f"{form}: {count}" for form, count in sorted(form_counts.items()))
        console.print(f"  Forms:    {breakdown}")

    console.print()


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

    table = Table(title="Ingested Filings")
    table.add_column("Ticker", style="cyan")
    table.add_column("Form", style="green")
    table.add_column("Filing Date")
    table.add_column("Accession Number", style="dim")
    table.add_column("Chunks", justify="right")
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
        raise typer.Exit(code=1)

    console.print(
        f"\n  Filing:  {filing.ticker} {filing.form_type} ({filing.filing_date})"
        f"\n  Chunks:  {filing.chunk_count}"
        f"\n  Accession: {filing.accession_number}\n"
    )

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
        raise typer.Exit(code=1) from None

    console.print(
        f"[green]Removed:[/green] {filing.ticker} {filing.form_type} "
        f"({filing.filing_date}) — {chunks_deleted} chunks deleted"
    )
