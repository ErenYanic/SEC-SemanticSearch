"""
Status endpoint — database overview and statistics.

Provides ``GET /api/status/`` returning filing count, chunk count,
per-ticker and per-form breakdowns.  Mirrors the CLI ``manage status``
command output.
"""

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
    stats = registry.get_statistics()
    chunk_count = chroma.collection_count()

    ticker_breakdown = [
        TickerBreakdown(
            ticker=ts.ticker,
            filings=ts.filings,
            chunks=ts.chunks,
            forms=ts.forms,
        )
        for ts in stats.ticker_breakdown
    ]

    return StatusResponse(
        filing_count=stats.filing_count,
        max_filings=settings.database.max_filings,
        chunk_count=chunk_count,
        tickers=stats.tickers,
        form_breakdown=stats.form_breakdown,
        ticker_breakdown=ticker_breakdown,
    )