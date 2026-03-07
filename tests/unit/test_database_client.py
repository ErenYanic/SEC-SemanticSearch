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
