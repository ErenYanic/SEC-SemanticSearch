"""Tests for core domain data classes.

These types are the foundation of the entire pipeline — every module
depends on them. We verify normalisation, immutability, computed
properties, factory methods, and metadata conversion to catch contract
violations early.
"""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from sec_semantic_search.core.types import (
    Chunk,
    ContentType,
    FilingIdentifier,
    IngestResult,
    SearchResult,
    Segment,
)


# -----------------------------------------------------------------------
# ContentType enum
# -----------------------------------------------------------------------


class TestContentType:
    """Verify enum values match doc2dict output strings."""

    def test_text_value(self):
        assert ContentType.TEXT.value == "text"

    def test_textsmall_value(self):
        assert ContentType.TEXTSMALL.value == "textsmall"

    def test_table_value(self):
        assert ContentType.TABLE.value == "table"

    def test_from_string(self):
        """ContentType("text") should produce ContentType.TEXT.

        This is how SearchResult.from_chromadb_result reconstructs
        the enum from stored metadata strings.
        """
        assert ContentType("text") is ContentType.TEXT
        assert ContentType("table") is ContentType.TABLE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ContentType("invalid")


# -----------------------------------------------------------------------
# FilingIdentifier
# -----------------------------------------------------------------------


class TestFilingIdentifier:
    """Verify normalisation, immutability, and date formatting."""

    def test_normalises_ticker_to_uppercase(self):
        fid = FilingIdentifier(
            ticker="aapl",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            accession_number="0000320193-24-000001",
        )
        assert fid.ticker == "AAPL"

    def test_normalises_form_type_to_uppercase(self):
        fid = FilingIdentifier(
            ticker="MSFT",
            form_type="10-k",
            filing_date=date(2024, 7, 30),
            accession_number="0000789019-24-000001",
        )
        assert fid.form_type == "10-K"

    def test_frozen_immutability(self, sample_filing_id):
        """Frozen dataclass should reject attribute assignment."""
        with pytest.raises(FrozenInstanceError):
            sample_filing_id.ticker = "MSFT"

    def test_date_str_iso_format(self, sample_filing_id):
        assert sample_filing_id.date_str == "2024-11-01"

    def test_equality(self):
        """Two identifiers with the same fields should be equal."""
        fid1 = FilingIdentifier("AAPL", "10-K", date(2024, 1, 1), "ACC-001")
        fid2 = FilingIdentifier("aapl", "10-k", date(2024, 1, 1), "ACC-001")
        assert fid1 == fid2

    def test_hashable(self):
        """Frozen dataclasses are hashable — usable as dict keys."""
        fid = FilingIdentifier("AAPL", "10-K", date(2024, 1, 1), "ACC-001")
        d = {fid: "test"}
        assert d[fid] == "test"


# -----------------------------------------------------------------------
# Segment
# -----------------------------------------------------------------------


class TestSegment:
    """Segment is a simple data holder — verify construction."""

    def test_construction(self, sample_filing_id):
        seg = Segment(
            path="Part I > Item 1",
            content_type=ContentType.TEXT,
            content="Some business text.",
            filing_id=sample_filing_id,
        )
        assert seg.path == "Part I > Item 1"
        assert seg.content_type is ContentType.TEXT
        assert seg.content == "Some business text."
        assert seg.filing_id is sample_filing_id


# -----------------------------------------------------------------------
# Chunk
# -----------------------------------------------------------------------


class TestChunk:
    """Verify chunk_id format and metadata conversion."""

    def test_chunk_id_format(self, sample_filing_id):
        """chunk_id must be {TICKER}_{FORM}_{DATE}_{INDEX:03d}."""
        chunk = Chunk(
            content="text",
            path="Part I",
            content_type=ContentType.TEXT,
            filing_id=sample_filing_id,
            chunk_index=42,
        )
        assert chunk.chunk_id == "AAPL_10-K_2024-11-01_042"

    def test_chunk_id_zero_padded(self, sample_filing_id):
        """Index should be zero-padded to 3 digits."""
        chunk = Chunk(
            content="text",
            path="Part I",
            content_type=ContentType.TEXT,
            filing_id=sample_filing_id,
            chunk_index=0,
        )
        assert chunk.chunk_id.endswith("_000")

    def test_default_chunk_index(self, sample_filing_id):
        """Default chunk_index is 0."""
        chunk = Chunk(
            content="text",
            path="Part I",
            content_type=ContentType.TEXT,
            filing_id=sample_filing_id,
        )
        assert chunk.chunk_index == 0

    def test_to_metadata_keys(self, sample_chunks):
        """to_metadata() must return all keys ChromaDB expects."""
        meta = sample_chunks[0].to_metadata()
        expected_keys = {
            "path",
            "content_type",
            "ticker",
            "form_type",
            "filing_date",
            "accession_number",
        }
        assert set(meta.keys()) == expected_keys

    def test_to_metadata_values(self, sample_chunks):
        """Verify metadata values are correctly extracted."""
        meta = sample_chunks[0].to_metadata()
        assert meta["ticker"] == "AAPL"
        assert meta["form_type"] == "10-K"
        assert meta["filing_date"] == "2024-11-01"
        assert meta["content_type"] == "text"
        assert meta["path"] == "Part I > Item 1 > Business"

    def test_to_metadata_all_strings(self, sample_chunks):
        """ChromaDB metadata values must all be strings."""
        meta = sample_chunks[0].to_metadata()
        for key, value in meta.items():
            assert isinstance(value, str), f"meta[{key!r}] is {type(value).__name__}, not str"


# -----------------------------------------------------------------------
# SearchResult
# -----------------------------------------------------------------------


class TestSearchResult:
    """Verify the ChromaDB factory method and distance-to-similarity."""

    def test_from_chromadb_result_similarity(self):
        """distance=0.3 should become similarity=0.7."""
        result = SearchResult.from_chromadb_result(
            document="some text",
            metadata={
                "path": "Part I",
                "content_type": "text",
                "ticker": "AAPL",
                "form_type": "10-K",
                "filing_date": "2024-11-01",
                "accession_number": "ACC-001",
            },
            distance=0.3,
            chunk_id="AAPL_10-K_2024-11-01_000",
        )
        assert result.similarity == pytest.approx(0.7)

    def test_from_chromadb_result_zero_distance(self):
        """Perfect match (distance=0.0) gives similarity=1.0."""
        result = SearchResult.from_chromadb_result(
            document="exact match",
            metadata={"path": "X", "content_type": "text", "ticker": "T", "form_type": "F"},
            distance=0.0,
        )
        assert result.similarity == pytest.approx(1.0)

    def test_from_chromadb_result_metadata_extraction(self):
        """All metadata fields should be correctly mapped."""
        metadata = {
            "path": "Part II > Item 8",
            "content_type": "table",
            "ticker": "MSFT",
            "form_type": "10-Q",
            "filing_date": "2024-06-30",
            "accession_number": "ACC-999",
        }
        result = SearchResult.from_chromadb_result(
            document="financial data",
            metadata=metadata,
            distance=0.5,
        )
        assert result.content == "financial data"
        assert result.path == "Part II > Item 8"
        assert result.content_type is ContentType.TABLE
        assert result.ticker == "MSFT"
        assert result.form_type == "10-Q"
        assert result.filing_date == "2024-06-30"
        assert result.accession_number == "ACC-999"

    def test_from_chromadb_result_missing_optional_fields(self):
        """Missing optional metadata should default gracefully."""
        result = SearchResult.from_chromadb_result(
            document="text",
            metadata={"path": "X", "content_type": "text", "ticker": "T", "form_type": "F"},
            distance=0.4,
        )
        assert result.filing_date is None
        assert result.accession_number is None
        assert result.chunk_id is None


# -----------------------------------------------------------------------
# IngestResult
# -----------------------------------------------------------------------


class TestIngestResult:
    """IngestResult is a statistics container — verify construction."""

    def test_construction(self, sample_filing_id):
        result = IngestResult(
            filing_id=sample_filing_id,
            segment_count=354,
            chunk_count=357,
            duration_seconds=31.2,
        )
        assert result.segment_count == 354
        assert result.chunk_count == 357
        assert result.duration_seconds == pytest.approx(31.2)
        assert result.filing_id is sample_filing_id
