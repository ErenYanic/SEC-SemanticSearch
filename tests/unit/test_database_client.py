"""
Unit tests for ChromaDBClient._build_where_filter().

This static method builds ChromaDB where-clause dicts from optional
filter parameters.  It has four code paths (0, 1, 2, 3 conditions)
and the $and wrapper logic — all previously untested.
"""

import pytest

from sec_semantic_search.database.client import ChromaDBClient


class TestBuildWhereFilter:
    """_build_where_filter() constructs ChromaDB metadata filters."""

    def test_no_filters_returns_none(self):
        """No filters should produce None (ChromaDB interprets as 'match all')."""
        assert ChromaDBClient._build_where_filter() is None

    def test_ticker_only(self):
        result = ChromaDBClient._build_where_filter(ticker="AAPL")
        assert result == {"ticker": "AAPL"}

    def test_form_type_only(self):
        result = ChromaDBClient._build_where_filter(form_type="10-K")
        assert result == {"form_type": "10-K"}

    def test_accession_number_only(self):
        result = ChromaDBClient._build_where_filter(accession_number="ACC-001")
        assert result == {"accession_number": "ACC-001"}

    def test_two_conditions_uses_and(self):
        """Two conditions should be wrapped in $and."""
        result = ChromaDBClient._build_where_filter(ticker="AAPL", form_type="10-K")
        assert "$and" in result
        assert len(result["$and"]) == 2
        assert {"ticker": "AAPL"} in result["$and"]
        assert {"form_type": "10-K"} in result["$and"]

    def test_three_conditions_uses_and(self):
        result = ChromaDBClient._build_where_filter(
            ticker="AAPL", form_type="10-K", accession_number="ACC-001"
        )
        assert "$and" in result
        assert len(result["$and"]) == 3

    def test_ticker_uppercased(self):
        """Ticker should be uppercased inside the filter."""
        result = ChromaDBClient._build_where_filter(ticker="aapl")
        assert result == {"ticker": "AAPL"}

    def test_form_type_uppercased(self):
        result = ChromaDBClient._build_where_filter(form_type="10-q")
        assert result == {"form_type": "10-Q"}

    def test_none_values_ignored(self):
        """Explicitly passing None should behave like not passing at all."""
        result = ChromaDBClient._build_where_filter(
            ticker=None, form_type=None, accession_number=None
        )
        assert result is None

    def test_empty_string_treated_as_falsy(self):
        """Empty strings are falsy and should be ignored."""
        result = ChromaDBClient._build_where_filter(ticker="", form_type="")
        assert result is None


class TestBuildWhereFilterMultiValue:
    """_build_where_filter() supports list[str] for multi-value matching."""

    def test_single_item_list_uses_equality(self):
        """A one-element list should produce a simple equality filter."""
        result = ChromaDBClient._build_where_filter(ticker=["AAPL"])
        assert result == {"ticker": "AAPL"}

    def test_multi_item_list_uses_in_operator(self):
        """Multiple items should produce a $in filter."""
        result = ChromaDBClient._build_where_filter(ticker=["AAPL", "MSFT"])
        assert result == {"ticker": {"$in": ["AAPL", "MSFT"]}}

    def test_multi_ticker_uppercased(self):
        result = ChromaDBClient._build_where_filter(ticker=["aapl", "msft"])
        assert result == {"ticker": {"$in": ["AAPL", "MSFT"]}}

    def test_multi_form_type_uses_in(self):
        result = ChromaDBClient._build_where_filter(form_type=["10-K", "10-Q"])
        assert result == {"form_type": {"$in": ["10-K", "10-Q"]}}

    def test_multi_form_type_uppercased(self):
        result = ChromaDBClient._build_where_filter(form_type=["10-k", "10-q"])
        assert result == {"form_type": {"$in": ["10-K", "10-Q"]}}

    def test_multi_accession_uses_in(self):
        result = ChromaDBClient._build_where_filter(
            accession_number=["ACC-001", "ACC-002"]
        )
        assert result == {"accession_number": {"$in": ["ACC-001", "ACC-002"]}}

    def test_mixed_list_and_scalar(self):
        """A list ticker + scalar form_type should combine via $and."""
        result = ChromaDBClient._build_where_filter(
            ticker=["AAPL", "MSFT"], form_type="10-K"
        )
        assert "$and" in result
        assert {"ticker": {"$in": ["AAPL", "MSFT"]}} in result["$and"]
        assert {"form_type": "10-K"} in result["$and"]

    def test_all_three_multi_value(self):
        """All filters as lists should produce $and with $in conditions."""
        result = ChromaDBClient._build_where_filter(
            ticker=["AAPL", "MSFT"],
            form_type=["10-K", "10-Q"],
            accession_number=["ACC-001", "ACC-002"],
        )
        assert "$and" in result
        assert len(result["$and"]) == 3

    def test_empty_list_treated_as_falsy(self):
        """An empty list should be treated as no filter."""
        result = ChromaDBClient._build_where_filter(ticker=[], form_type=[])
        assert result is None


class TestBuildWhereFilterDateRange:
    """_build_where_filter() supports date-range filtering via $gte/$lte on filing_date_int."""

    def test_start_date_only(self):
        """start_date produces a $gte condition on filing_date_int."""
        result = ChromaDBClient._build_where_filter(start_date="2023-01-01")
        assert result == {"filing_date_int": {"$gte": 20230101}}

    def test_end_date_only(self):
        """end_date produces a $lte condition on filing_date_int."""
        result = ChromaDBClient._build_where_filter(end_date="2023-12-31")
        assert result == {"filing_date_int": {"$lte": 20231231}}

    def test_both_dates_produces_and(self):
        """start_date + end_date produces $and with both conditions."""
        result = ChromaDBClient._build_where_filter(
            start_date="2023-01-01", end_date="2023-12-31"
        )
        assert "$and" in result
        assert {"filing_date_int": {"$gte": 20230101}} in result["$and"]
        assert {"filing_date_int": {"$lte": 20231231}} in result["$and"]

    def test_date_with_ticker(self):
        """Date range combined with ticker filter uses $and."""
        result = ChromaDBClient._build_where_filter(
            ticker="AAPL", start_date="2023-01-01"
        )
        assert "$and" in result
        assert {"ticker": "AAPL"} in result["$and"]
        assert {"filing_date_int": {"$gte": 20230101}} in result["$and"]

    def test_date_with_all_filters(self):
        """Date range combined with all other filters."""
        result = ChromaDBClient._build_where_filter(
            ticker="AAPL",
            form_type="10-K",
            accession_number="ACC-001",
            start_date="2023-01-01",
            end_date="2023-12-31",
        )
        assert "$and" in result
        assert len(result["$and"]) == 5

    def test_none_dates_ignored(self):
        """None date values should not add conditions."""
        result = ChromaDBClient._build_where_filter(
            ticker="AAPL", start_date=None, end_date=None
        )
        assert result == {"ticker": "AAPL"}

    def test_empty_string_dates_ignored(self):
        """Empty string dates should be treated as falsy."""
        result = ChromaDBClient._build_where_filter(start_date="", end_date="")
        assert result is None


class TestDateStrToInt:
    """_date_str_to_int() converts ISO date strings to YYYYMMDD integers."""

    def test_standard_date(self):
        assert ChromaDBClient._date_str_to_int("2023-01-15") == 20230115

    def test_first_day_of_year(self):
        assert ChromaDBClient._date_str_to_int("2020-01-01") == 20200101

    def test_last_day_of_year(self):
        assert ChromaDBClient._date_str_to_int("2025-12-31") == 20251231

    def test_preserves_chronological_ordering(self):
        """Integer ordering must match chronological ordering."""
        dates = ["2022-06-15", "2023-01-01", "2023-12-31", "2024-03-05"]
        ints = [ChromaDBClient._date_str_to_int(d) for d in dates]
        assert ints == sorted(ints)
