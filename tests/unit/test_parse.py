"""
Tests for the FilingParser pipeline component.

FilingParser wraps doc2dict to parse SEC filing HTML into Segment
objects. These tests verify segment extraction, hierarchical path
building, content type classification, table formatting, and error
handling.

Because doc2dict is a third-party library whose exact output format
may change across versions, we test the *contract* (segments are
produced, paths are hierarchical, content types are correct) rather
than exact string matching where possible.
"""

import pytest

from sec_semantic_search.core.exceptions import ParseError
from sec_semantic_search.core.types import ContentType
from sec_semantic_search.pipeline.parse import FilingParser


@pytest.fixture
def parser() -> FilingParser:
    return FilingParser()


class TestBasicParsing:
    """Core parsing: valid HTML should produce segments."""

    def test_produces_segments(self, parser, sample_html, sample_filing_id):
        """Valid HTML with text content should produce at least one segment."""
        segments = parser.parse(sample_html, sample_filing_id)
        assert len(segments) > 0

    def test_segments_have_content(self, parser, sample_html, sample_filing_id):
        """Every segment should have non-empty content."""
        segments = parser.parse(sample_html, sample_filing_id)
        for seg in segments:
            assert seg.content.strip(), f"Segment at {seg.path!r} has empty content"

    def test_segments_have_filing_id(self, parser, sample_html, sample_filing_id):
        """Every segment should reference the filing identifier."""
        segments = parser.parse(sample_html, sample_filing_id)
        for seg in segments:
            assert seg.filing_id is sample_filing_id

    def test_segments_have_valid_content_type(self, parser, sample_html, sample_filing_id):
        """Every segment's content_type should be a ContentType enum member."""
        segments = parser.parse(sample_html, sample_filing_id)
        for seg in segments:
            assert isinstance(seg.content_type, ContentType)


class TestHierarchicalPaths:
    """The parser should build hierarchical paths using ' > ' separator."""

    def test_path_separator(self, parser, sample_html, sample_filing_id):
        """Paths with nesting should use ' > ' as the separator."""
        segments = parser.parse(sample_html, sample_filing_id)
        # At least some segments should have hierarchical paths
        nested = [s for s in segments if FilingParser.PATH_SEPARATOR in s.path]
        # doc2dict may or may not produce nested paths from our simple HTML,
        # so we just verify the separator is used if nesting occurs
        for seg in nested:
            parts = seg.path.split(FilingParser.PATH_SEPARATOR)
            assert all(part.strip() for part in parts), (
                f"Path has empty parts: {seg.path!r}"
            )

    def test_no_empty_path(self, parser, sample_html, sample_filing_id):
        """No segment should have a completely empty path."""
        segments = parser.parse(sample_html, sample_filing_id)
        for seg in segments:
            assert seg.path, "Segment has empty path"


class TestTableFormatting:
    """The _format_table method converts table data to pipe-delimited text."""

    def test_dict_table_with_data(self, parser):
        """Dict-format table with a data field should produce piped rows."""
        table = {
            "data": [
                ["Revenue", "394,328", "383,285"],
                ["Net Income", "93,736", "96,995"],
            ],
        }
        result = parser._format_table(table)
        assert "Revenue | 394,328 | 383,285" in result
        assert "Net Income | 93,736 | 96,995" in result

    def test_dict_table_with_title(self, parser):
        """Table title should appear in the formatted output."""
        table = {
            "title": "Consolidated Balance Sheet",
            "data": [["Assets", "100"]],
        }
        result = parser._format_table(table)
        assert "Consolidated Balance Sheet" in result

    def test_dict_table_with_footnotes(self, parser):
        """Footnotes should be appended after the data rows."""
        table = {
            "data": [["Revenue", "100"]],
            "footnotes": ["(1) In millions of USD"],
        }
        result = parser._format_table(table)
        assert "(1) In millions of USD" in result

    def test_list_table(self, parser):
        """List-of-rows format should produce piped rows."""
        table = [
            ["Header1", "Header2"],
            ["Value1", "Value2"],
        ]
        result = parser._format_table(table)
        assert "Header1 | Header2" in result
        assert "Value1 | Value2" in result

    def test_empty_table_returns_empty(self, parser):
        """An empty dict should produce an empty string."""
        assert parser._format_table({}) == ""

    def test_non_dict_non_list_returns_empty(self, parser):
        """A non-dict, non-list value should produce an empty string."""
        assert parser._format_table("not a table") == ""


class TestErrorHandling:
    """Parser should raise ParseError for invalid inputs."""

    def test_empty_string_raises(self, parser, sample_filing_id):
        with pytest.raises(ParseError, match="Empty HTML content"):
            parser.parse("", sample_filing_id)

    def test_whitespace_only_raises(self, parser, sample_filing_id):
        with pytest.raises(ParseError, match="Empty HTML content"):
            parser.parse("   \n\t  ", sample_filing_id)


class TestContentTypeExtraction:
    """Verify that different HTML elements map to correct ContentType."""

    def test_paragraph_text(self, parser, sample_filing_id):
        """<p> elements should produce TEXT or TEXTSMALL segments."""
        html = "<html><body><p>A paragraph of regular text content.</p></body></html>"
        segments = parser.parse(html, sample_filing_id)
        text_types = {ContentType.TEXT, ContentType.TEXTSMALL}
        assert any(s.content_type in text_types for s in segments)

    def test_table_content(self, parser, sample_filing_id):
        """<table> elements should produce TABLE segments."""
        html = """
        <html><body>
        <table>
            <tr><td>Revenue</td><td>100</td></tr>
            <tr><td>Expenses</td><td>80</td></tr>
        </table>
        </body></html>
        """
        segments = parser.parse(html, sample_filing_id)
        table_segments = [s for s in segments if s.content_type is ContentType.TABLE]
        assert len(table_segments) > 0, "No TABLE segments extracted from <table> HTML"
