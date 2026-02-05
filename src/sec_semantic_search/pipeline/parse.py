"""SEC filing HTML parser using doc2dict.

This module parses SEC filing HTML into semantically meaningful segments.
It uses doc2dict for initial HTML parsing and then recursively extracts
content with hierarchical paths.

Usage:
    from sec_semantic_search.pipeline import FilingParser

    parser = FilingParser()
    segments = parser.parse(html_content, filing_id)
"""

from typing import Any

from doc2dict import html2dict

from sec_semantic_search.core import (
    ContentType,
    FilingIdentifier,
    ParseError,
    Segment,
    get_logger,
)

logger = get_logger(__name__)


class FilingParser:
    """Parses SEC filing HTML into structured segments.

    This class wraps doc2dict to parse filing HTML and extract semantically
    meaningful segments. Each segment includes its hierarchical path in the
    document (e.g., "Part I > Item 1A > Risk Factors").

    Content types extracted:
        - text: Regular paragraph text
        - textsmall: Smaller text elements (footnotes, captions)
        - table: Tabular data converted to text representation

    Example:
        >>> parser = FilingParser()
        >>> segments = parser.parse(html_content, filing_id)
        >>> print(f"Extracted {len(segments)} segments")
    """

    # Path separator for hierarchical paths
    PATH_SEPARATOR = " > "

    def parse(
        self,
        html_content: str,
        filing_id: FilingIdentifier,
    ) -> list[Segment]:
        """Parse filing HTML into segments.

        Args:
            html_content: Raw HTML content from SEC EDGAR.
            filing_id: Identifier for the source filing.

        Returns:
            List of Segment objects with content and metadata.

        Raises:
            ParseError: If HTML parsing fails.

        Example:
            >>> segments = parser.parse(html_content, filing_id)
            >>> for seg in segments[:3]:
            ...     print(f"[{seg.content_type.value}] {seg.path}")
        """
        if not html_content or not html_content.strip():
            raise ParseError(
                "Empty HTML content",
                details="Cannot parse empty or whitespace-only content.",
            )

        logger.info(
            "Parsing %s %s (%s characters)",
            filing_id.ticker,
            filing_id.form_type,
            f"{len(html_content):,}",
        )

        try:
            parsed = html2dict(html_content)
        except Exception as e:
            raise ParseError(
                "Failed to parse HTML with doc2dict",
                details=str(e),
            ) from e

        if not parsed:
            raise ParseError(
                "doc2dict returned empty result",
                details="The HTML may be malformed or unsupported.",
            )

        # Extract segments recursively
        segments: list[Segment] = []

        # Handle the 'document' wrapper if present (common in SEC filings)
        root = parsed.get("document", parsed)

        if isinstance(root, dict):
            for key in root:
                self._extract_segments(
                    dct=root[key],
                    path="",
                    filing_id=filing_id,
                    segments=segments,
                )

        if not segments:
            raise ParseError(
                "No segments extracted from HTML",
                details="The document structure may be unsupported.",
            )

        logger.info(
            "Extracted %d segments from %s %s",
            len(segments),
            filing_id.ticker,
            filing_id.form_type,
        )

        return segments

    def _extract_segments(
        self,
        dct: Any,
        path: str,
        filing_id: FilingIdentifier,
        segments: list[Segment],
    ) -> None:
        """Recursively extract segments from parsed dictionary.

        This method traverses the doc2dict output tree, building hierarchical
        paths and extracting content from text, textsmall, and table fields.

        Args:
            dct: Current dictionary node (or non-dict value to skip).
            path: Current hierarchical path (e.g., "Part I > Item 1").
            filing_id: Source filing identifier.
            segments: List to append extracted segments to (modified in place).
        """
        if not isinstance(dct, dict):
            return

        # Build current path from 'title' if present
        current_path = path
        if "title" in dct and isinstance(dct["title"], str):
            title = dct["title"].strip()
            if title:
                current_path = (
                    f"{path}{self.PATH_SEPARATOR}{title}" if path else title
                )

        # Extract text content
        for key in ("text", "textsmall"):
            if key in dct and isinstance(dct[key], str):
                content = dct[key].strip()
                if content:
                    content_type = (
                        ContentType.TEXT if key == "text" else ContentType.TEXTSMALL
                    )
                    segments.append(
                        Segment(
                            path=current_path or "(root)",
                            content_type=content_type,
                            content=content,
                            filing_id=filing_id,
                        )
                    )

        # Extract table content
        if "table" in dct:
            table_content = self._format_table(dct["table"])
            if table_content:
                segments.append(
                    Segment(
                        path=current_path or "(root)",
                        content_type=ContentType.TABLE,
                        content=table_content,
                        filing_id=filing_id,
                    )
                )

        # Recurse into nested contents
        contents = dct.get("contents", {})
        if isinstance(contents, dict):
            for key in contents:
                self._extract_segments(
                    dct=contents[key],
                    path=current_path,
                    filing_id=filing_id,
                    segments=segments,
                )

    def _format_table(self, table: Any) -> str:
        """Convert table data to readable text representation.

        Tables are formatted as pipe-delimited rows, making them both
        human-readable and suitable for embedding.

        Args:
            table: Table data from doc2dict (dict or list format).

        Returns:
            Formatted table as string, or empty string if invalid.
        """
        parts: list[str] = []

        if isinstance(table, dict):
            # Handle structured table format
            if table.get("title"):
                parts.append(str(table["title"]))

            if table.get("preamble"):
                parts.append(str(table["preamble"]))

            if table.get("data"):
                for row in table["data"]:
                    if isinstance(row, (list, tuple)):
                        parts.append(" | ".join(str(cell) for cell in row))
                    else:
                        parts.append(str(row))

            if table.get("footnotes"):
                for footnote in table["footnotes"]:
                    parts.append(str(footnote))

            if table.get("postamble"):
                parts.append(str(table["postamble"]))

        elif isinstance(table, list):
            # Handle simple list-of-rows format
            for row in table:
                if isinstance(row, (list, tuple)):
                    parts.append(" | ".join(str(cell) for cell in row))
                else:
                    parts.append(str(row))

        return "\n".join(parts).strip()
