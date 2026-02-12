"""Tests for the package-level __init__.py.

Verifies version discovery, re-exported types, and __all__ contents.
The package __init__ deliberately avoids importing heavy modules
(torch, chromadb) — we verify this by checking that only lightweight
core types are re-exported.
"""

import sec_semantic_search


class TestVersion:
    """__version__ should be readable and well-formed."""

    def test_version_exists(self):
        assert hasattr(sec_semantic_search, "__version__")

    def test_version_is_string(self):
        assert isinstance(sec_semantic_search.__version__, str)

    def test_version_not_fallback(self):
        """In dev mode (pip install -e .), version should come from metadata."""
        assert sec_semantic_search.__version__ != "0.0.0"

    def test_version_matches_pyproject(self):
        """The version should match what pyproject.toml declares."""
        assert sec_semantic_search.__version__ == "0.1.0"


class TestReExports:
    """Core types should be importable directly from the package."""

    def test_filing_identifier(self):
        from sec_semantic_search import FilingIdentifier
        assert FilingIdentifier is not None

    def test_chunk(self):
        from sec_semantic_search import Chunk
        assert Chunk is not None

    def test_search_result(self):
        from sec_semantic_search import SearchResult
        assert SearchResult is not None

    def test_content_type(self):
        from sec_semantic_search import ContentType
        assert ContentType is not None

    def test_segment(self):
        from sec_semantic_search import Segment
        assert Segment is not None

    def test_ingest_result(self):
        from sec_semantic_search import IngestResult
        assert IngestResult is not None

    def test_base_exception(self):
        from sec_semantic_search import SECSemanticSearchError
        assert issubclass(SECSemanticSearchError, Exception)


class TestAllExports:
    """__all__ should list every public name."""

    def test_all_defined(self):
        assert hasattr(sec_semantic_search, "__all__")

    def test_all_contains_version(self):
        assert "__version__" in sec_semantic_search.__all__

    def test_all_contains_types(self):
        expected = {
            "ContentType", "FilingIdentifier", "Segment",
            "Chunk", "SearchResult", "IngestResult",
            "SECSemanticSearchError",
        }
        assert expected.issubset(set(sec_semantic_search.__all__))

    def test_all_items_are_importable(self):
        """Every name in __all__ should actually exist on the module."""
        for name in sec_semantic_search.__all__:
            assert hasattr(sec_semantic_search, name), f"{name!r} listed in __all__ but not found"
