"""
Tests for API Pydantic request/response schemas.

Validates field constraints, normalisation (uppercase tickers/form types),
default values, and custom validators — all via direct model instantiation
with no HTTP involved.
"""

import pytest
from pydantic import ValidationError

from sec_semantic_search.api.schemas import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    ClearAllResponse,
    DeleteResponse,
    ErrorResponse,
    FilingListResponse,
    FilingSchema,
    GPUStatusResponse,
    GPUUnloadResponse,
    IngestRequest,
    IngestResultSchema,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
    StatusResponse,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
    TaskStatus,
    TickerBreakdown,
)


# -----------------------------------------------------------------------
# ErrorResponse
# -----------------------------------------------------------------------


class TestErrorResponse:
    """ErrorResponse carries structured error information."""

    def test_required_fields(self):
        resp = ErrorResponse(error="not_found", message="Filing not found")
        assert resp.error == "not_found"
        assert resp.message == "Filing not found"

    def test_optional_fields_default_none(self):
        resp = ErrorResponse(error="err", message="msg")
        assert resp.details is None
        assert resp.hint is None

    def test_all_fields_populated(self):
        resp = ErrorResponse(
            error="database_error",
            message="Failed",
            details="Traceback",
            hint="Check permissions",
        )
        assert resp.details == "Traceback"
        assert resp.hint == "Check permissions"


# -----------------------------------------------------------------------
# Status schemas
# -----------------------------------------------------------------------


class TestTickerBreakdown:
    """Per-ticker statistics."""

    def test_valid(self):
        tb = TickerBreakdown(ticker="AAPL", filings=3, chunks=100, forms=["10-K"])
        assert tb.ticker == "AAPL"

    def test_filings_ge_zero(self):
        with pytest.raises(ValidationError):
            TickerBreakdown(ticker="X", filings=-1, chunks=0)


class TestStatusResponse:
    """Database overview response."""

    def test_defaults(self):
        resp = StatusResponse(filing_count=0, max_filings=100, chunk_count=0)
        assert resp.tickers == []
        assert resp.form_breakdown == {}
        assert resp.ticker_breakdown == []

    def test_filing_count_ge_zero(self):
        with pytest.raises(ValidationError):
            StatusResponse(filing_count=-1, max_filings=100, chunk_count=0)

    def test_max_filings_ge_one(self):
        with pytest.raises(ValidationError):
            StatusResponse(filing_count=0, max_filings=0, chunk_count=0)

    def test_chunk_count_ge_zero(self):
        with pytest.raises(ValidationError):
            StatusResponse(filing_count=0, max_filings=1, chunk_count=-1)


# -----------------------------------------------------------------------
# Filing schemas
# -----------------------------------------------------------------------


class TestFilingSchema:
    """Single filing record."""

    def test_all_fields(self):
        f = FilingSchema(
            ticker="AAPL",
            form_type="10-K",
            filing_date="2024-11-01",
            accession_number="0000320193-24-000001",
            chunk_count=100,
            ingested_at="2024-11-15T10:00:00",
        )
        assert f.ticker == "AAPL"
        assert f.chunk_count == 100

    def test_chunk_count_ge_zero(self):
        with pytest.raises(ValidationError):
            FilingSchema(
                ticker="X", form_type="10-K", filing_date="2024-01-01",
                accession_number="x", chunk_count=-1, ingested_at="x",
            )


class TestFilingListResponse:
    """Filing list with total."""

    def test_empty(self):
        resp = FilingListResponse(filings=[], total=0)
        assert resp.filings == []
        assert resp.total == 0


class TestDeleteResponse:
    """Single filing delete response."""

    def test_valid(self):
        resp = DeleteResponse(accession_number="x", chunks_deleted=50)
        assert resp.chunks_deleted == 50


class TestBulkDeleteRequest:
    """Bulk delete request with form_type validation."""

    def test_both_none_is_valid_at_schema_level(self):
        req = BulkDeleteRequest()
        assert req.ticker is None
        assert req.form_type is None

    def test_form_type_normalised_to_uppercase(self):
        req = BulkDeleteRequest(form_type="10-k")
        assert req.form_type == "10-K"

    def test_invalid_form_type_raises(self):
        with pytest.raises(ValidationError, match="form_type must be"):
            BulkDeleteRequest(form_type="8-K")

    def test_none_form_type_ok(self):
        req = BulkDeleteRequest(ticker="AAPL", form_type=None)
        assert req.form_type is None


class TestBulkDeleteResponse:
    """Bulk delete response."""

    def test_defaults(self):
        resp = BulkDeleteResponse(filings_deleted=0, chunks_deleted=0)
        assert resp.tickers_affected == []


class TestClearAllResponse:
    """Clear all response."""

    def test_valid(self):
        resp = ClearAllResponse(filings_deleted=5, chunks_deleted=500)
        assert resp.filings_deleted == 5


# -----------------------------------------------------------------------
# Search schemas
# -----------------------------------------------------------------------


class TestSearchResultSchema:
    """Single search result."""

    def test_valid(self):
        r = SearchResultSchema(
            content="text", path="Part I", content_type="text",
            ticker="AAPL", form_type="10-K", similarity=0.5,
        )
        assert r.similarity == 0.5

    def test_similarity_range(self):
        with pytest.raises(ValidationError):
            SearchResultSchema(
                content="x", path="x", content_type="text",
                ticker="X", form_type="10-K", similarity=1.5,
            )

    def test_optional_fields_default_none(self):
        r = SearchResultSchema(
            content="x", path="x", content_type="text",
            ticker="X", form_type="10-K", similarity=0.1,
        )
        assert r.filing_date is None
        assert r.accession_number is None
        assert r.chunk_id is None


class TestSearchRequest:
    """Search request with validation and normalisation."""

    def test_defaults(self):
        req = SearchRequest(query="test")
        assert req.top_k == 5
        assert req.min_similarity == 0.0
        assert req.ticker is None
        assert req.form_type is None

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_top_k_min(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", top_k=0)

    def test_top_k_max(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", top_k=101)

    def test_top_k_in_range(self):
        req = SearchRequest(query="test", top_k=100)
        assert req.top_k == 100

    def test_ticker_normalised_uppercase(self):
        req = SearchRequest(query="test", ticker="aapl")
        assert req.ticker == "AAPL"

    def test_form_type_normalised_uppercase(self):
        req = SearchRequest(query="test", form_type="10-q")
        assert req.form_type == "10-Q"

    def test_invalid_form_type_raises(self):
        with pytest.raises(ValidationError, match="form_type must be"):
            SearchRequest(query="test", form_type="8-K")

    def test_min_similarity_out_of_range(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_similarity=1.5)

    def test_min_similarity_negative(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="test", min_similarity=-0.1)


class TestSearchResponse:
    """Search response."""

    def test_valid(self):
        resp = SearchResponse(
            query="test", results=[], total_results=0, search_time_ms=1.5,
        )
        assert resp.search_time_ms == 1.5


# -----------------------------------------------------------------------
# Ingest schemas
# -----------------------------------------------------------------------


class TestIngestRequest:
    """Ingest request with normalisation and validation."""

    def test_defaults(self):
        req = IngestRequest(tickers=["AAPL"])
        assert req.form_types == ["10-K", "10-Q"]
        assert req.count_mode == "latest"
        assert req.count is None
        assert req.year is None

    def test_tickers_normalised_uppercase(self):
        req = IngestRequest(tickers=["aapl", " msft "])
        assert req.tickers == ["AAPL", "MSFT"]

    def test_empty_tickers_raises(self):
        with pytest.raises(ValidationError):
            IngestRequest(tickers=[])

    def test_invalid_form_types_raises(self):
        with pytest.raises(ValidationError, match="Unsupported form types"):
            IngestRequest(tickers=["AAPL"], form_types=["8-K"])

    def test_form_types_normalised_uppercase(self):
        req = IngestRequest(tickers=["AAPL"], form_types=["10-k", "10-q"])
        assert req.form_types == ["10-K", "10-Q"]

    def test_invalid_count_mode_raises(self):
        with pytest.raises(ValidationError, match="count_mode must be"):
            IngestRequest(tickers=["AAPL"], count_mode="invalid")

    def test_valid_count_modes(self):
        for mode in ("latest", "total", "per_form"):
            req = IngestRequest(tickers=["AAPL"], count_mode=mode)
            assert req.count_mode == mode

    def test_count_ge_one(self):
        with pytest.raises(ValidationError):
            IngestRequest(tickers=["AAPL"], count=0)

    def test_year_ge_1993(self):
        with pytest.raises(ValidationError):
            IngestRequest(tickers=["AAPL"], year=1992)

    def test_year_valid(self):
        req = IngestRequest(tickers=["AAPL"], year=2024)
        assert req.year == 2024


class TestTaskProgress:
    """Task progress snapshot."""

    def test_defaults(self):
        p = TaskProgress()
        assert p.step_index == 0
        assert p.step_total == 5
        assert p.filings_done == 0

    def test_step_index_ge_zero(self):
        with pytest.raises(ValidationError):
            TaskProgress(step_index=-1)


class TestIngestResultSchema:
    """Per-filing ingest result."""

    def test_valid(self):
        r = IngestResultSchema(
            ticker="AAPL", form_type="10-K", filing_date="2024-11-01",
            accession_number="x", segment_count=100, chunk_count=110,
            duration_seconds=5.3,
        )
        assert r.segment_count == 100


class TestTaskStatus:
    """Full task status."""

    def test_defaults(self):
        ts = TaskStatus(
            task_id="abc", status="pending",
            tickers=["AAPL"], form_types=["10-K"],
            progress=TaskProgress(),
        )
        assert ts.results == []
        assert ts.error is None
        assert ts.started_at is None
        assert ts.completed_at is None


class TestTaskResponse:
    """Immediate ingest creation response."""

    def test_valid(self):
        resp = TaskResponse(task_id="abc", websocket_url="/ws/ingest/abc")
        assert resp.status == "pending"
        assert resp.websocket_url == "/ws/ingest/abc"


class TestTaskListResponse:
    """Task list response."""

    def test_empty(self):
        resp = TaskListResponse(tasks=[], total=0)
        assert resp.tasks == []


# -----------------------------------------------------------------------
# GPU / resources schemas
# -----------------------------------------------------------------------


class TestGPUStatusResponse:
    """GPU status response."""

    def test_not_loaded(self):
        resp = GPUStatusResponse(
            model_loaded=False, model_name="test-model",
        )
        assert resp.device is None
        assert resp.approximate_vram_mb is None

    def test_loaded(self):
        resp = GPUStatusResponse(
            model_loaded=True, device="cuda",
            model_name="test-model", approximate_vram_mb=1200,
        )
        assert resp.device == "cuda"
        assert resp.approximate_vram_mb == 1200


class TestGPUUnloadResponse:
    """GPU unload response."""

    def test_unloaded(self):
        resp = GPUUnloadResponse(status="unloaded")
        assert resp.status == "unloaded"

    def test_already_unloaded(self):
        resp = GPUUnloadResponse(status="already_unloaded")
        assert resp.status == "already_unloaded"