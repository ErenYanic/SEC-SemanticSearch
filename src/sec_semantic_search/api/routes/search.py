"""
Search endpoint for semantic search over ingested SEC filings.

Provides a single route:
    - ``POST /api/search/`` — run a semantic search query with optional filters
"""

import time

from fastapi import APIRouter, Depends, HTTPException

from sec_semantic_search.api.dependencies import get_search_engine
from sec_semantic_search.api.schemas import (
    ErrorResponse,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
)
from sec_semantic_search.core import SearchError, get_logger
from sec_semantic_search.search import SearchEngine

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=SearchResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Semantic search over filings",
)
async def search(
    body: SearchRequest,
    engine: SearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """
    Search ingested SEC filings using a natural language query.

    The query is embedded with the same model used during ingestion
    and matched against stored chunks via cosine similarity.  Results
    are returned ranked by similarity (highest first).

    Accepts optional filters for ticker, form type, minimum similarity
    threshold, and accession number (filing-specific search).
    """
    start = time.perf_counter()

    try:
        results = engine.search(
            query=body.query,
            top_k=body.top_k,
            ticker=body.ticker,
            form_type=body.form_type,
            min_similarity=body.min_similarity,
            accession_number=body.accession_number,
        )
    except SearchError as exc:
        # Empty query is a validation error (400); everything else is 500.
        if "empty" in exc.message.lower():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": exc.message,
                    "details": exc.details,
                    "hint": "Provide a non-empty search query.",
                },
            ) from exc

        raise HTTPException(
            status_code=500,
            detail={
                "error": "search_error",
                "message": exc.message,
                "details": exc.details,
                "hint": "Ensure filings have been ingested and the database is accessible.",
            },
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    result_schemas = [
        SearchResultSchema(
            content=r.content,
            path=r.path,
            content_type=r.content_type.value,
            ticker=r.ticker,
            form_type=r.form_type,
            similarity=r.similarity,
            filing_date=r.filing_date,
            accession_number=r.accession_number,
            chunk_id=r.chunk_id,
        )
        for r in results
    ]

    logger.info(
        "Search '%s' returned %d result(s) in %.1f ms",
        body.query[:80],
        len(result_schemas),
        elapsed_ms,
    )

    return SearchResponse(
        query=body.query,
        results=result_schemas,
        total_results=len(result_schemas),
        search_time_ms=round(elapsed_ms, 1),
    )