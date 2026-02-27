"""
Filing management endpoints — list, retrieve, and delete ingested filings.

Provides full CRUD (minus create — that's ingest) for the filing registry:
    - ``GET    /api/filings/``            — list filings with optional filters
    - ``GET    /api/filings/{accession}`` — get a single filing by accession number
    - ``DELETE /api/filings/{accession}`` — delete a single filing (ChromaDB first, then SQLite)
    - ``POST   /api/filings/bulk-delete`` — bulk delete by ticker/form_type filter
    - ``DELETE /api/filings/``            — clear all filings (requires ``confirm=true``)
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from sec_semantic_search.api.dependencies import get_chroma, get_registry
from sec_semantic_search.api.schemas import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    ClearAllResponse,
    DeleteResponse,
    ErrorResponse,
    FilingListResponse,
    FilingSchema,
)
from sec_semantic_search.core import DatabaseError, get_logger
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.database.metadata import FilingRecord

logger = get_logger(__name__)

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


# ---------------------------------------------------------------------------
# Delete helpers
# ---------------------------------------------------------------------------


def _delete_filings(
    filings: list[FilingRecord],
    *,
    chroma: ChromaDBClient,
    registry: MetadataRegistry,
) -> int:
    """
    Delete a list of filings from both stores (ChromaDB first, then SQLite).

    Returns the total number of chunks deleted.
    """
    total_chunks = 0
    for filing in filings:
        chunks_deleted = chroma.delete_filing(filing.accession_number)
        registry.remove_filing(filing.accession_number)
        total_chunks += chunks_deleted
        logger.info(
            "Deleted %s %s (%s) — %d chunks",
            filing.ticker,
            filing.form_type,
            filing.filing_date,
            chunks_deleted,
        )
    return total_chunks


# ---------------------------------------------------------------------------
# Delete endpoints (W1.3)
# ---------------------------------------------------------------------------


@router.delete(
    "/{accession}",
    response_model=DeleteResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete a single filing",
)
async def delete_filing(
    accession: str,
    registry: MetadataRegistry = Depends(get_registry),
    chroma: ChromaDBClient = Depends(get_chroma),
) -> DeleteResponse:
    """
    Delete a single filing by accession number from both stores.

    Removes vector data from ChromaDB first, then the metadata row from
    SQLite.  Returns the number of chunks deleted.
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

    try:
        chunks_deleted = chroma.delete_filing(accession)
        registry.remove_filing(accession)
    except DatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "database_error",
                "message": f"Failed to delete filing: {accession}",
                "details": exc.details,
                "hint": "Check that the data directory is writable.",
            },
        ) from exc

    logger.info(
        "Deleted filing %s (%s %s) — %d chunks",
        accession,
        record.ticker,
        record.form_type,
        chunks_deleted,
    )
    return DeleteResponse(
        accession_number=accession,
        chunks_deleted=chunks_deleted,
    )


@router.post(
    "/bulk-delete",
    response_model=BulkDeleteResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Bulk delete filings by filter",
)
async def bulk_delete(
    body: BulkDeleteRequest,
    registry: MetadataRegistry = Depends(get_registry),
    chroma: ChromaDBClient = Depends(get_chroma),
) -> BulkDeleteResponse:
    """
    Delete all filings matching the given ticker and/or form_type filter.

    At least one filter (``ticker`` or ``form_type``) must be provided.
    Returns the number of filings and chunks deleted.
    """
    if body.ticker is None and body.form_type is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "At least one filter is required.",
                "hint": (
                    "Provide 'ticker' and/or 'form_type'. "
                    "To delete everything, use DELETE /api/filings/?confirm=true instead."
                ),
            },
        )

    filings = registry.list_filings(
        ticker=body.ticker.upper() if body.ticker else None,
        form_type=body.form_type,  # Already uppercased by validator
    )

    if not filings:
        return BulkDeleteResponse(
            filings_deleted=0,
            chunks_deleted=0,
            tickers_affected=[],
        )

    try:
        total_chunks = _delete_filings(
            filings, chroma=chroma, registry=registry,
        )
    except DatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "database_error",
                "message": "Bulk delete failed.",
                "details": exc.details,
                "hint": "Check that the data directory is writable.",
            },
        ) from exc

    tickers_affected = sorted({f.ticker for f in filings})
    return BulkDeleteResponse(
        filings_deleted=len(filings),
        chunks_deleted=total_chunks,
        tickers_affected=tickers_affected,
    )


@router.delete(
    "/",
    response_model=ClearAllResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Clear all filings",
)
async def clear_all(
    confirm: bool = Query(
        False, description="Safety flag — must be true to proceed"
    ),
    registry: MetadataRegistry = Depends(get_registry),
    chroma: ChromaDBClient = Depends(get_chroma),
) -> ClearAllResponse:
    """
    Delete every filing from both stores.

    Requires ``confirm=true`` as a safety measure to prevent accidental
    data loss.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "message": "This will delete ALL filings. Pass ?confirm=true to proceed.",
                "hint": "Add '?confirm=true' to the request URL.",
            },
        )

    filings = registry.list_filings()

    if not filings:
        return ClearAllResponse(filings_deleted=0, chunks_deleted=0)

    try:
        total_chunks = _delete_filings(
            filings, chroma=chroma, registry=registry,
        )
    except DatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "database_error",
                "message": "Clear all failed.",
                "details": exc.details,
                "hint": "Check that the data directory is writable.",
            },
        ) from exc

    logger.info(
        "Cleared database: %d filing(s), %d chunks deleted",
        len(filings),
        total_chunks,
    )
    return ClearAllResponse(
        filings_deleted=len(filings),
        chunks_deleted=total_chunks,
    )