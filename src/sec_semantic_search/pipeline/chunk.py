"""
Text chunking for SEC filings.

This module splits long segments into smaller chunks suitable for embedding.
It uses sentence-boundary splitting to ensure chunks don't cut mid-sentence.

Usage:
    from sec_semantic_search.pipeline import TextChunker

    chunker = TextChunker()
    chunks = chunker.chunk_segments(segments)
"""

import re

from sec_semantic_search.config import get_settings
from sec_semantic_search.core import Chunk, ChunkingError, Segment, get_logger

logger = get_logger(__name__)


class TextChunker:
    """
    Splits segments into embedding-ready chunks.

    This class implements sentence-boundary aware chunking to ensure
    that text is split at natural boundaries rather than mid-sentence.

    The chunking algorithm:
        1. If segment fits within token limit, keep as-is
        2. Otherwise, split on sentence boundaries (. ! ?)
        3. Accumulate sentences until adding another would exceed limit
        4. Tolerance band allows slight overrun to avoid tiny final chunks

    Attributes:
        token_limit: Maximum tokens per chunk (from settings)
        tolerance: Acceptable overrun tolerance (from settings)

    Example:
        >>> chunker = TextChunker()
        >>> chunks = chunker.chunk_segments(segments)
        >>> print(f"Created {len(chunks)} chunks")
    """

    # Sentence boundary pattern: split after . ! ? followed by whitespace
    SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")

    def __init__(
        self,
        token_limit: int | None = None,
        tolerance: int | None = None,
    ) -> None:
        """
        Initialise the chunker with configurable limits.

        Args:
            token_limit: Max tokens per chunk. If None, uses settings.
            tolerance: Acceptable overrun. If None, uses settings.
        """
        settings = get_settings()
        self.token_limit = token_limit or settings.chunking.token_limit
        self.tolerance = tolerance or settings.chunking.tolerance

        logger.debug(
            "TextChunker initialised: limit=%d, tolerance=%d",
            self.token_limit,
            self.tolerance,
        )

    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count using whitespace splitting.

        This is a simple heuristic that works well for English text.
        More accurate tokenisation would require the actual model's
        tokeniser, but whitespace splitting is sufficient for chunking.

        Args:
            text: Text to count tokens in.

        Returns:
            Approximate token count.
        """
        return len(text.split())

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks respecting sentence boundaries.

        Args:
            text: Text content to split.

        Returns:
            List of text chunks.
        """
        total_tokens = self._count_tokens(text)

        # If text already fits, return as single chunk
        if total_tokens <= self.token_limit:
            return [text]

        # Split on sentence boundaries
        sentences = self.SENTENCE_PATTERN.split(text)

        chunks: list[str] = []
        current_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # Check if adding this sentence would exceed limit + tolerance
            # If so, finalise current chunk (unless it's empty)
            if (
                current_tokens + sentence_tokens > self.token_limit + self.tolerance
                and current_sentences
            ):
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Flush remaining sentences
        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks

    def chunk_segment(self, segment: Segment, start_index: int = 0) -> list[Chunk]:
        """
        Split a single segment into chunks.

        Args:
            segment: Segment to chunk.
            start_index: Starting chunk index for this segment.

        Returns:
            List of Chunk objects with sequential indices.
        """
        text_chunks = self._chunk_text(segment.content)

        return [
            Chunk(
                content=text,
                path=segment.path,
                content_type=segment.content_type,
                filing_id=segment.filing_id,
                chunk_index=start_index + i,
            )
            for i, text in enumerate(text_chunks)
        ]

    def chunk_segments(self, segments: list[Segment]) -> list[Chunk]:
        """
        Chunk all segments from a filing.

        This is the main entry point for chunking. It processes all
        segments and assigns sequential chunk indices across the
        entire filing.

        Args:
            segments: List of segments from FilingParser.

        Returns:
            List of Chunk objects ready for embedding.

        Raises:
            ChunkingError: If segments list is empty.

        Example:
            >>> chunks = chunker.chunk_segments(segments)
            >>> for chunk in chunks[:3]:
            ...     print(f"[{chunk.chunk_index}] {chunk.path[:50]}...")
        """
        if not segments:
            raise ChunkingError(
                "No segments to chunk",
                details="Received empty segments list.",
            )

        filing_id = segments[0].filing_id

        logger.info(
            "Chunking %d segments from %s %s",
            len(segments),
            filing_id.ticker,
            filing_id.form_type,
        )

        chunks: list[Chunk] = []
        current_index = 0

        for segment in segments:
            segment_chunks = self.chunk_segment(segment, start_index=current_index)
            chunks.extend(segment_chunks)
            current_index += len(segment_chunks)

        # Log statistics
        token_counts = [self._count_tokens(c.content) for c in chunks]
        min_tokens = min(token_counts)
        max_tokens = max(token_counts)
        avg_tokens = sum(token_counts) / len(token_counts)
        over_limit = sum(1 for t in token_counts if t > self.token_limit)

        logger.info(
            "Created %d chunks from %d segments (tokens: %d-%d, avg %.0f, %d over limit)",
            len(chunks),
            len(segments),
            min_tokens,
            max_tokens,
            avg_tokens,
            over_limit,
        )

        return chunks
