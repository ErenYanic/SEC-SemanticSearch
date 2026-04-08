"""
Extended schema validation tests — covers gaps in the original test_schemas.py.

Adds tests for:
    - SearchRequest with whitespace-only query
    - IngestRequest date fields
    - BulkDeleteRequest ticker normalisation
    - SearchResultSchema similarity boundary values
"""

import pytest
from pydantic import ValidationError

from sec_semantic_search.api.schemas import (
    BulkDeleteRequest,
    IngestRequest,
    SearchRequest,
    SearchResultSchema,
)


class TestSearchRequestExtended:
    """Additional SearchRequest edge cases."""

    def test_whitespace_only_query_accepted(self):
        """Whitespace-only passes min_length=1 (no strip_whitespace on schema)."""
        req = SearchRequest(query="   ")
        assert req.query == "   "

    def test_very_long_query_rejected(self):
        """Queries over 2000 characters should be rejected (DoS prevention)."""
        with pytest.raises(ValidationError, match="at most 2000"):
            SearchRequest(query="a" * 10000)

    def test_none_ticker_and_form_type(self):
        req = SearchRequest(query="test", ticker=None, form_type=None)
        assert req.ticker is None
        assert req.form_type is None


class TestIngestRequestDates:
    """IngestRequest date validation."""

    def test_start_date_accepted(self):
        req = IngestRequest(tickers=["AAPL"], start_date="2023-01-01")
        assert req.start_date == "2023-01-01"

    def test_end_date_accepted(self):
        req = IngestRequest(tickers=["AAPL"], end_date="2024-12-31")
        assert req.end_date == "2024-12-31"

    def test_both_dates_accepted(self):
        req = IngestRequest(tickers=["AAPL"], start_date="2023-01-01", end_date="2024-12-31")
        assert req.start_date == "2023-01-01"
        assert req.end_date == "2024-12-31"

    def test_dates_default_none(self):
        req = IngestRequest(tickers=["AAPL"])
        assert req.start_date is None
        assert req.end_date is None

    def test_duplicate_tickers_preserved(self):
        """Schema does not deduplicate — that's the backend's job."""
        req = IngestRequest(tickers=["AAPL", "AAPL"])
        assert len(req.tickers) == 2

    def test_max_tickers_reasonable(self):
        """Sanity: large ticker list with valid format should be accepted."""
        # Generate valid 1–5 letter tickers.
        tickers = [f"T{chr(65 + i % 26)}" for i in range(50)]
        req = IngestRequest(tickers=tickers)
        assert len(req.tickers) == 50


class TestBulkDeleteRequestExtended:
    """BulkDeleteRequest ticker normalisation."""

    def test_ticker_normalised_to_uppercase(self):
        """BulkDeleteRequest now normalises ticker to uppercase at schema level."""
        req = BulkDeleteRequest(ticker="aapl")
        assert req.ticker == "AAPL"

    def test_ticker_whitespace_stripped(self):
        """BulkDeleteRequest strips whitespace and normalises ticker."""
        req = BulkDeleteRequest(ticker=" MSFT ")
        assert req.ticker == "MSFT"

    def test_both_filters(self):
        req = BulkDeleteRequest(ticker="AAPL", form_type="10-K")
        assert req.ticker == "AAPL"
        assert req.form_type == "10-K"


class TestSearchResultSchemaBoundary:
    """Similarity boundary values."""

    def test_similarity_zero(self):
        r = SearchResultSchema(
            content="x",
            path="x",
            content_type="text",
            ticker="X",
            form_type="10-K",
            similarity=0.0,
        )
        assert r.similarity == 0.0

    def test_similarity_one(self):
        r = SearchResultSchema(
            content="x",
            path="x",
            content_type="text",
            ticker="X",
            form_type="10-K",
            similarity=1.0,
        )
        assert r.similarity == 1.0

    def test_similarity_negative_raises(self):
        with pytest.raises(ValidationError):
            SearchResultSchema(
                content="x",
                path="x",
                content_type="text",
                ticker="X",
                form_type="10-K",
                similarity=-0.01,
            )

    def test_similarity_above_one_raises(self):
        with pytest.raises(ValidationError):
            SearchResultSchema(
                content="x",
                path="x",
                content_type="text",
                ticker="X",
                form_type="10-K",
                similarity=1.01,
            )
