"""Tests for the FilingFetcher pipeline component.

FilingFetcher wraps edgartools to fetch SEC filings over the network.
We mock edgartools' Company and set_identity so tests run without
network access. The class has substantial testable logic in its helper
methods: form type validation, date parsing, date filter formatting,
and the FilingInfo dataclass conversion.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.core.exceptions import FetchError
from sec_semantic_search.pipeline.fetch import FilingFetcher, FilingInfo


# -----------------------------------------------------------------------
# FilingInfo dataclass
# -----------------------------------------------------------------------


class TestFilingInfo:
    """FilingInfo is a lightweight preview returned by list_available()."""

    def test_to_identifier(self):
        """to_identifier() should convert to a FilingIdentifier."""
        info = FilingInfo(
            ticker="aapl",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            accession_number="ACC-001",
            company_name="Apple Inc.",
        )
        fid = info.to_identifier()
        assert fid.ticker == "AAPL"  # Normalised
        assert fid.form_type == "10-K"
        assert fid.filing_date == date(2024, 11, 1)
        assert fid.accession_number == "ACC-001"


# -----------------------------------------------------------------------
# Helper method tests (via a fetcher with mocked edgartools)
# -----------------------------------------------------------------------


@pytest.fixture
def fetcher():
    """A FilingFetcher with mocked EDGAR identity configuration."""
    with patch("sec_semantic_search.pipeline.fetch.set_identity"):
        return FilingFetcher()


class TestValidateFormType:
    """_validate_form_type() normalises and validates."""

    def test_valid_10k(self, fetcher):
        assert fetcher._validate_form_type("10-K") == "10-K"

    def test_valid_10q_lowercase(self, fetcher):
        assert fetcher._validate_form_type("10-q") == "10-Q"

    def test_invalid_form_raises(self, fetcher):
        with pytest.raises(FetchError, match="Unsupported form type"):
            fetcher._validate_form_type("8-K")


class TestParseFilingDate:
    """_parse_filing_date() handles both date objects and strings."""

    def test_date_object_passthrough(self, fetcher):
        d = date(2024, 6, 15)
        assert fetcher._parse_filing_date(d) is d

    def test_string_parsing(self, fetcher):
        result = fetcher._parse_filing_date("2024-06-15")
        assert result == date(2024, 6, 15)

    def test_invalid_string_raises(self, fetcher):
        with pytest.raises(ValueError):
            fetcher._parse_filing_date("not-a-date")


class TestFormatDateFilter:
    """_format_date_filter() builds edgartools date range strings."""

    def test_both_dates(self, fetcher):
        result = fetcher._format_date_filter("2020-01-01", "2024-12-31")
        assert result == "2020-01-01:2024-12-31"

    def test_start_only(self, fetcher):
        result = fetcher._format_date_filter("2020-01-01", None)
        assert result == "2020-01-01:"

    def test_end_only(self, fetcher):
        result = fetcher._format_date_filter(None, "2024-12-31")
        assert result == ":2024-12-31"

    def test_neither(self, fetcher):
        result = fetcher._format_date_filter(None, None)
        assert result is None

    def test_date_objects(self, fetcher):
        result = fetcher._format_date_filter(
            date(2020, 1, 1), date(2024, 12, 31)
        )
        assert result == "2020-01-01:2024-12-31"


class TestFetchLatest:
    """fetch_latest() delegates to fetch_one(index=0)."""

    def test_delegates_to_fetch_one(self, fetcher):
        """fetch_latest should call fetch_one with index=0."""
        mock_filing = MagicMock()
        mock_filing.accession_no = "ACC-001"
        mock_filing.filing_date = date(2024, 11, 1)
        mock_filing.html.return_value = "<html>content</html>"

        mock_company = MagicMock()
        mock_filings = MagicMock()
        mock_filings.__len__ = lambda self: 1
        mock_filings.__iter__ = lambda self: iter([mock_filing])
        mock_filings.__bool__ = lambda self: True
        mock_company.get_filings.return_value = mock_filings

        with patch.object(fetcher, "_get_company", return_value=mock_company):
            filing_id, html = fetcher.fetch_latest("AAPL", "10-K")

        assert filing_id.ticker == "AAPL"
        assert html == "<html>content</html>"


class TestFetchOneIndexOutOfRange:
    """fetch_one() should raise FetchError when index exceeds available filings."""

    def test_index_out_of_range(self, fetcher):
        mock_company = MagicMock()
        mock_filings = MagicMock()
        mock_filings.__len__ = lambda self: 2
        mock_filings.__iter__ = lambda self: iter([MagicMock(), MagicMock()])
        mock_filings.__bool__ = lambda self: True
        mock_company.get_filings.return_value = mock_filings

        with patch.object(fetcher, "_get_company", return_value=mock_company):
            with pytest.raises(FetchError, match="Index 5 out of range"):
                fetcher.fetch_one("AAPL", "10-K", index=5)


class TestGetCompanyError:
    """_get_company() should wrap edgartools errors as FetchError."""

    def test_invalid_ticker(self, fetcher):
        with patch(
            "sec_semantic_search.pipeline.fetch.Company",
            side_effect=Exception("Unknown ticker"),
        ):
            with pytest.raises(FetchError, match="Invalid ticker"):
                fetcher._get_company("INVALIDTICKER")
