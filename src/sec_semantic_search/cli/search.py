"""Search command for querying ingested SEC filings."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from sec_semantic_search.core import SearchError
from sec_semantic_search.search import SearchEngine

console = Console()

# Maximum characters to display per result in the table.
_CONTENT_PREVIEW_LIMIT = 1000
_SECTION_PATH_LIMIT = 500


def _similarity_text(similarity: float) -> Text:
    """
    Return a colour-coded similarity percentage.

    Green for >= 40%, yellow for >= 25%, dim otherwise.
    These thresholds reflect typical cosine similarity ranges
    from the embedding model where raw scores are relatively low.
    """
    pct = f"{similarity:.1%}"
    if similarity >= 0.40:
        return Text(pct, style="bold green")
    if similarity >= 0.25:
        return Text(pct, style="yellow")
    return Text(pct, style="dim")


def search(
    query: Annotated[str, typer.Argument(help="Natural language search query.")],
    top: Annotated[
        Optional[int],
        typer.Option("--top", "-t", help="Number of results to return."),
    ] = None,
    ticker: Annotated[
        Optional[str],
        typer.Option("--ticker", "-k", help="Filter by ticker symbol."),
    ] = None,
    form: Annotated[
        Optional[str],
        typer.Option("--form", "-f", help="Filter by form type (10-K or 10-Q)."),
    ] = None,
) -> None:
    """
    Search ingested SEC filings with a natural language query.

    Examples:

        sec-search search "risk factors related to supply chain"

        sec-search search "revenue recognition" -t 10 -k AAPL

        sec-search search "liquidity" -f 10-Q
    """
    with console.status("Searching..."):
        try:
            engine = SearchEngine()
            results = engine.search(
                query=query,
                top_k=top,
                ticker=ticker.upper() if ticker else None,
                form_type=form.upper() if form else None,
            )
        except SearchError as e:
            console.print(f"[red]Search failed:[/red] {e.message}")
            if e.details:
                console.print(f"  [dim]{e.details}[/dim]")
            console.print(
                "  [dim italic]Hint: Ensure filings have been ingested with "
                "'sec-search ingest add'.[/dim italic]"
            )
            raise typer.Exit(code=1) from None

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        console.print(
            "[dim italic]Hint: Try a broader query, or check that filings are ingested "
            "with 'sec-search manage status'.[/dim italic]"
        )
        return

    console.print(f"\n[bold]Found {len(results)} result(s)[/bold] for: [italic]{query}[/italic]\n")

    table = Table(show_lines=True, expand=True, border_style="dim")
    table.add_column("#", style="bold", width=3, justify="right")
    table.add_column("Similarity", width=10, justify="right")
    table.add_column("Source", style="cyan", width=20, no_wrap=True)
    table.add_column("Section", style="dim", max_width=30)
    table.add_column("Content")

    for i, result in enumerate(results, 1):
        # Source: ticker, form type, and date in one compact column.
        source = f"{result.ticker} {result.form_type}"
        if result.filing_date:
            source += f"\n{result.filing_date}"

        # Truncate long content for display.
        content = result.content
        if len(content) > _CONTENT_PREVIEW_LIMIT:
            content = content[:_CONTENT_PREVIEW_LIMIT] + "..."

        # Truncate long section paths for display.
        section = result.path
        if len(section) > _SECTION_PATH_LIMIT:
            section = section[:_SECTION_PATH_LIMIT] + "..."

        table.add_row(
            str(i),
            _similarity_text(result.similarity),
            source,
            section,
            content,
        )

    console.print(table)
