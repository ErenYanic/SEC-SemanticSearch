"""
Status endpoint — database overview and statistics.

Provides ``GET /api/status/`` returning filing count, chunk count,
per-ticker and per-form breakdowns.  Mirrors the CLI ``manage status``
command output.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends

from sec_semantic_search.api.dependencies import get_chroma, get_registry
from sec_semantic_search.api.schemas import StatusResponse, TickerBreakdown
from sec_semantic_search.config import get_settings
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry

router = APIRouter()


@router.get(
    "/",
    response_model=StatusResponse,
    summary="Database overview",
)
async def status(
    registry: MetadataRegistry = Depends(get_registry),
    chroma: ChromaDBClient = Depends(get_chroma),
) -> StatusResponse:
    """
    Return a full overview of database contents and capacity.

    Includes filing count, chunk count, unique tickers, form type
    breakdown, and per-ticker statistics.
    """
    settings = get_settings()
    filings = registry.list_filings()
    chunk_count = chroma.collection_count()

    # Aggregate per-ticker and per-form statistics from the filing list.
    tickers_set: set[str] = set()
    form_counts: dict[str, int] = defaultdict(int)
    ticker_data: dict[str, dict] = defaultdict(
        lambda: {"filings": 0, "chunks": 0, "forms": set()}
    )

    for f in filings:
        tickers_set.add(f.ticker)
        form_counts[f.form_type] += 1
        ticker_data[f.ticker]["filings"] += 1
        ticker_data[f.ticker]["chunks"] += f.chunk_count
        ticker_data[f.ticker]["forms"].add(f.form_type)

    ticker_breakdown = [
        TickerBreakdown(
            ticker=ticker,
            filings=data["filings"],
            chunks=data["chunks"],
            forms=sorted(data["forms"]),
        )
        for ticker, data in sorted(ticker_data.items())
    ]

    return StatusResponse(
        filing_count=len(filings),
        max_filings=settings.database.max_filings,
        chunk_count=chunk_count,
        tickers=sorted(tickers_set),
        form_breakdown=dict(sorted(form_counts.items())),
        ticker_breakdown=ticker_breakdown,
    )