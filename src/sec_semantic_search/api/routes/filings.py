"""
Filing management endpoints — list and retrieve ingested filings.

Provides read-only access to the SQLite metadata registry:
    - ``GET /api/filings/``          — list filings with optional filters
    - ``GET /api/filings/{accession}`` — get a single filing by accession number

Delete endpoints are added in W1.3.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from sec_semantic_search.api.dependencies import get_registry
from sec_semantic_search.api.schemas import (
    ErrorResponse,
    FilingListResponse,
    FilingSchema,
)
from sec_semantic_search.database import MetadataRegistry
from sec_semantic_search.database.metadata import FilingRecord

router = APIRouter()


def _record_to_schema(record: FilingRecord) -> FilingSchema:
    """Convert a database ``FilingRecord`` to an API ``FilingSchema``."""
    return FilingSchema(
        ticker=record.ticker,
        form_type=record.form_type,
        filing_date=record.filing_date,
        accession_number=record.accession_number,
        chunk_count=record.chunk_count,
        ingested_at=record.ingested_at,
    )


@router.get(
    "/",
    response_model=FilingListResponse,
    summary="List ingested filings",
)
async def list_filings(
    registry: MetadataRegistry = Depends(get_registry),
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    form_type: str | None = Query(None, description="Filter by form type (10-K or 10-Q)"),
    sort_by: Literal["filing_date", "ticker", "form_type", "chunk_count", "ingested_at"] = Query(
        "filing_date", description="Column to sort by"
    ),
    order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
) -> FilingListResponse:
    """
    List all ingested filings with optional filters and sorting.

    Results are returned in the order specified by ``sort_by`` and ``order``.
    The underlying registry always returns filings ordered by filing_date
    descending; additional sorting is applied in-memory.
    """
    records = registry.list_filings(
        ticker=ticker.upper() if ticker else None,
        form_type=form_type.upper() if form_type else None,
    )

    # Apply sorting.  The registry returns filing_date DESC by default,
    # so we only need to re-sort when the caller requests something else.
    if sort_by != "filing_date" or order != "desc":
        reverse = order == "desc"
        records.sort(key=lambda r: getattr(r, sort_by), reverse=reverse)

    schemas = [_record_to_schema(r) for r in records]
    return FilingListResponse(filings=schemas, total=len(schemas))


@router.get(
    "/{accession}",
    response_model=FilingSchema,
    responses={404: {"model": ErrorResponse}},
    summary="Get a single filing",
)
async def get_filing(
    accession: str,
    registry: MetadataRegistry = Depends(get_registry),
) -> FilingSchema:
    """
    Retrieve a single filing record by accession number.

    Returns 404 if the filing is not found in the registry.
    """
    record = registry.get_filing(accession)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Filing not found: {accession}",
                "hint": "Use GET /api/filings/ to list available accession numbers.",
            },
        )
    return _record_to_schema(record)