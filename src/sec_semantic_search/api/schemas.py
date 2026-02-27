"""
Pydantic v2 request and response schemas for the SEC Semantic Search API.

Schemas are separate from the core dataclasses in ``sec_semantic_search.core``
to provide a stable, explicit API contract.  Internal representations may
change without affecting the API surface.

Naming convention:
    - Request schemas:  ``<Resource>Request`` (e.g. ``SearchRequest``)
    - Response schemas: ``<Resource>Response`` or ``<Resource>Schema``
    - Nested schemas:   plain names without suffix (e.g. ``TickerBreakdown``)

All datetime strings are ISO 8601.  Similarity scores are floats in [0.0, 1.0].
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared / error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """
    Structured error response returned for all 4xx and 5xx responses.

    Matches the CLI error format (error type, human message, optional hint).
    """

    error: str = Field(..., description="Machine-readable error type")
    message: str = Field(..., description="Human-readable error description")
    details: str | None = Field(None, description="Additional technical context")
    hint: str | None = Field(None, description="Suggested remediation action")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TickerBreakdown(BaseModel):
    """Per-ticker statistics for the status response."""

    ticker: str
    filings: int = Field(..., ge=0)
    chunks: int = Field(..., ge=0)
    forms: list[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    """
    Response for ``GET /api/status/``.

    Provides a full overview of database contents and capacity.
    """

    filing_count: int = Field(..., ge=0, description="Total ingested filings")
    max_filings: int = Field(..., ge=1, description="Configured maximum filing count")
    chunk_count: int = Field(..., ge=0, description="Total chunks in vector store")
    tickers: list[str] = Field(default_factory=list, description="Unique ticker symbols")
    form_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Filing count per form type (e.g. {'10-K': 5, '10-Q': 12})",
    )
    ticker_breakdown: list[TickerBreakdown] = Field(
        default_factory=list,
        description="Per-ticker filing and chunk statistics",
    )


# ---------------------------------------------------------------------------
# Filings
# ---------------------------------------------------------------------------


class FilingSchema(BaseModel):
    """
    A single filing record as returned by listing endpoints.

    Mirrors ``database.metadata.FilingRecord`` without the internal ``id``.
    """

    ticker: str
    form_type: str
    filing_date: str = Field(..., description="ISO date (YYYY-MM-DD)")
    accession_number: str
    chunk_count: int = Field(..., ge=0)
    ingested_at: str = Field(..., description="ISO 8601 UTC timestamp")


class FilingListResponse(BaseModel):
    """Response for ``GET /api/filings/``."""

    filings: list[FilingSchema]
    total: int = Field(..., ge=0)


class DeleteResponse(BaseModel):
    """Response for ``DELETE /api/filings/{accession}``."""

    accession_number: str
    chunks_deleted: int = Field(..., ge=0)


class BulkDeleteRequest(BaseModel):
    """Request body for ``POST /api/filings/bulk-delete``."""

    ticker: str | None = Field(None, description="Filter by ticker symbol")
    form_type: str | None = Field(None, description="Filter by form type (10-K or 10-Q)")

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v: str | None) -> str | None:
        """Normalise and validate form_type to uppercase."""
        if v is None:
            return None
        upper = v.upper()
        if upper not in ("10-K", "10-Q"):
            msg = "form_type must be '10-K' or '10-Q'"
            raise ValueError(msg)
        return upper


class BulkDeleteResponse(BaseModel):
    """Response for ``POST /api/filings/bulk-delete``."""

    filings_deleted: int = Field(..., ge=0)
    chunks_deleted: int = Field(..., ge=0)
    tickers_affected: list[str] = Field(default_factory=list)


class ClearAllResponse(BaseModel):
    """Response for ``DELETE /api/filings/?confirm=true``."""

    filings_deleted: int = Field(..., ge=0)
    chunks_deleted: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchResultSchema(BaseModel):
    """
    A single result from a semantic search query.

    Uses ``content_type`` as a plain string (not the ``ContentType`` enum)
    to keep the API contract stable and framework-agnostic.
    """

    content: str
    path: str
    content_type: str = Field(..., description="One of: 'text', 'textsmall', 'table'")
    ticker: str
    form_type: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    filing_date: str | None = Field(None, description="ISO date (YYYY-MM-DD)")
    accession_number: str | None = None
    chunk_id: str | None = None


class SearchRequest(BaseModel):
    """Request body for ``POST /api/search/``."""

    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(5, ge=1, le=100, description="Maximum number of results")
    ticker: str | None = Field(None, description="Filter to a specific ticker")
    form_type: str | None = Field(None, description="Filter to '10-K' or '10-Q'")
    min_similarity: float = Field(
        0.0, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    accession_number: str | None = Field(
        None, description="Restrict search to a single filing"
    )

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v: str | None) -> str | None:
        """Normalise form_type to uppercase."""
        if v is None:
            return None
        upper = v.upper()
        if upper not in ("10-K", "10-Q"):
            msg = "form_type must be '10-K' or '10-Q'"
            raise ValueError(msg)
        return upper

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str | None) -> str | None:
        """Normalise ticker to uppercase."""
        return v.upper() if v else None


class SearchResponse(BaseModel):
    """Response for ``POST /api/search/``."""

    query: str
    results: list[SearchResultSchema]
    total_results: int = Field(..., ge=0)
    search_time_ms: float = Field(..., ge=0.0, description="Wall-clock search time in ms")


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TaskProgress(BaseModel):
    """Progress snapshot for a running ingestion task."""

    current_ticker: str | None = None
    current_form_type: str | None = None
    step_label: str = Field("", description="Human-readable step description")
    step_index: int = Field(0, ge=0, description="Current pipeline step (0-based)")
    step_total: int = Field(5, ge=1, description="Total pipeline steps")
    filings_done: int = Field(0, ge=0)
    filings_total: int = Field(0, ge=0)
    filings_skipped: int = Field(0, ge=0)
    filings_failed: int = Field(0, ge=0)


class IngestResultSchema(BaseModel):
    """Result for a single filing that was successfully ingested."""

    ticker: str
    form_type: str
    filing_date: str
    accession_number: str
    segment_count: int = Field(..., ge=0)
    chunk_count: int = Field(..., ge=0)
    duration_seconds: float = Field(..., ge=0.0)


class TaskStatus(BaseModel):
    """
    Full status of an ingestion task.

    Returned by ``GET /api/ingest/tasks/{task_id}`` and pushed via
    WebSocket as the task progresses.
    """

    task_id: str
    status: str = Field(
        ..., description="One of: 'pending', 'running', 'completed', 'failed', 'cancelled'"
    )
    tickers: list[str]
    form_types: list[str]
    progress: TaskProgress
    results: list[IngestResultSchema] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IngestRequest(BaseModel):
    """
    Request body for ``POST /api/ingest/add`` and ``POST /api/ingest/batch``.

    Mirrors the CLI ``ingest add`` flags with explicit typing.
    """

    tickers: list[str] = Field(..., min_length=1, description="Ticker symbols to ingest")
    form_types: list[str] = Field(
        default=["10-K", "10-Q"],
        description="SEC form types to ingest",
    )
    count_mode: str = Field(
        "latest",
        description=(
            "'latest': 1 filing per form per ticker; "
            "'total': count filings shared across forms; "
            "'per_form': count filings per form type"
        ),
    )
    count: int | None = Field(
        None,
        ge=1,
        description="Number of filings (None = all matching when date filters active)",
    )
    year: int | None = Field(None, ge=1993, description="Filter to a specific filing year")
    start_date: str | None = Field(None, description="ISO date (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="ISO date (YYYY-MM-DD)")

    @field_validator("tickers")
    @classmethod
    def normalise_tickers(cls, v: list[str]) -> list[str]:
        """Normalise tickers to uppercase and strip whitespace."""
        return [t.upper().strip() for t in v if t.strip()]

    @field_validator("form_types")
    @classmethod
    def validate_form_types(cls, v: list[str]) -> list[str]:
        """Normalise and validate form types."""
        normalised = [f.upper().strip() for f in v]
        invalid = [f for f in normalised if f not in ("10-K", "10-Q")]
        if invalid:
            msg = f"Unsupported form types: {invalid}. Allowed: 10-K, 10-Q"
            raise ValueError(msg)
        return normalised

    @field_validator("count_mode")
    @classmethod
    def validate_count_mode(cls, v: str) -> str:
        """Validate count mode."""
        allowed = ("latest", "total", "per_form")
        if v not in allowed:
            msg = f"count_mode must be one of {allowed}"
            raise ValueError(msg)
        return v


class TaskResponse(BaseModel):
    """
    Immediate response when an ingest task is created.

    The caller uses ``task_id`` to poll status or connect via WebSocket.
    """

    task_id: str
    status: str = "pending"
    websocket_url: str = Field(..., description="WebSocket URL for real-time progress")


class TaskListResponse(BaseModel):
    """Response for ``GET /api/ingest/tasks``."""

    tasks: list[TaskStatus]
    total: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# GPU / resources
# ---------------------------------------------------------------------------


class GPUStatusResponse(BaseModel):
    """
    Response for ``GET /api/resources/gpu``.

    Reports whether the embedding model is loaded and on which device.
    """

    model_loaded: bool
    device: str | None = Field(None, description="'cuda' or 'cpu' when model is loaded")
    model_name: str
    approximate_vram_mb: int | None = Field(
        None,
        description="Approximate VRAM usage in MB (None if not loaded or CPU)",
    )