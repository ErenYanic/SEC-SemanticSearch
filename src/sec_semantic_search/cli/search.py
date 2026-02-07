"""Search command for querying ingested SEC filings."""

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from sec_semantic_search.core import SearchError
from sec_semantic_search.search import SearchEngine

console = Console()

# Maximum characters to display per result.
_CONTENT_PREVIEW_LIMIT = 500


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
    """Search ingested SEC filings with a natural language query."""
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
            raise typer.Exit(code=1) from None

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print(f"\n[bold]Found {len(results)} result(s)[/bold]\n")

    for i, result in enumerate(results, 1):
        # Build the header line with similarity and filing metadata.
        similarity_pct = f"{result.similarity:.1%}"
        header = (
            f"[bold]#{i}[/bold]  "
            f"[cyan]{similarity_pct}[/cyan] similarity  |  "
            f"{result.ticker} {result.form_type}"
        )
        if result.filing_date:
            header += f"  |  {result.filing_date}"

        # Truncate long content for display.
        content = result.content
        if len(content) > _CONTENT_PREVIEW_LIMIT:
            content = content[:_CONTENT_PREVIEW_LIMIT] + "..."

        # Build the panel body.
        body = Text()
        body.append(result.path, style="dim")
        body.append("\n\n")
        body.append(content)

        console.print(Panel(body, title=header, title_align="left", expand=True))
