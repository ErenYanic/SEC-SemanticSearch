"""
Tests for web interface helper functions.

Pure functions extracted from Streamlit page modules can be tested
without a running Streamlit server. Currently covers the similarity
colour helper used by the search page.
"""

from sec_semantic_search.web_deprecated.pages.search import _similarity_colour


# -----------------------------------------------------------------------
# _similarity_colour() — Streamlit colour thresholds
# -----------------------------------------------------------------------


class TestSimilarityColour:
    """_similarity_colour() returns colour names calibrated to embeddinggemma-300m."""

    def test_high_similarity_green(self):
        assert _similarity_colour(0.45) == "green"

    def test_boundary_green(self):
        """Exactly 0.40 should be green (inclusive threshold)."""
        assert _similarity_colour(0.40) == "green"

    def test_medium_similarity_orange(self):
        assert _similarity_colour(0.30) == "orange"

    def test_boundary_orange(self):
        """Exactly 0.25 should be orange (inclusive threshold)."""
        assert _similarity_colour(0.25) == "orange"

    def test_low_similarity_red(self):
        assert _similarity_colour(0.10) == "red"

    def test_boundary_red(self):
        """Just below the orange threshold should be red."""
        assert _similarity_colour(0.24) == "red"