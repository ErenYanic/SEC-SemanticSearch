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
        3. Accumulate sentences targeting ``token_limit ± tolerance`` — finalise
           early once the running chunk has reached ``token_limit - tolerance``,
           and never overflow past ``token_limit + tolerance``.
        4. Seed each subsequent chunk with trailing whole sentences from the
           previous one, up to the configured overlap budget. If even the last
           sentence exceeds the budget, that single sentence is reused whole
           (sentence-boundary invariant preserved — chunks never start
           mid-sentence).

    Attributes:
        token_limit: Maximum tokens per chunk (from settings)
        tolerance: Acceptable ± deviation around ``token_limit`` (from settings)
        overlap: Token budget reused at the start of each subsequent chunk

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
        overlap: int | None = None,
    ) -> None:
        """
        Initialise the chunker with configurable limits.

        Args:
            token_limit: Max tokens per chunk. If None, uses settings.
            tolerance: Acceptable ± deviation around ``token_limit``. If None, uses settings.
            overlap: Token budget reused at the start of each subsequent chunk.
                If None, uses settings. Pass ``0`` to disable overlap.
        """
        settings = get_settings()
        self.token_limit = token_limit if token_limit is not None else settings.chunking.token_limit
        self.tolerance = tolerance if tolerance is not None else settings.chunking.tolerance
        self.overlap = overlap if overlap is not None else settings.chunking.overlap

        if self.overlap < 0:
            raise ValueError("overlap must be ≥ 0")
        if self.overlap >= self.token_limit:
            raise ValueError(
                f"overlap ({self.overlap}) must be smaller than token_limit ({self.token_limit})"
            )

        logger.debug(
            "TextChunker initialised: limit=%d, tolerance=±%d, overlap=%d",
            self.token_limit,
            self.tolerance,
            self.overlap,
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

    def _chunk_text(self, text: str) -> list[tuple[str, int]]:
        """
        Split text into chunks respecting sentence boundaries.

        Targets a chunk size of ``token_limit ± tolerance``: finalise as soon as
        the running chunk has reached ``token_limit - tolerance`` (early-stop),
        and never let it grow past ``token_limit + tolerance`` (hard cap). Each
        subsequent chunk is seeded with trailing whole sentences from the
        previous one, up to ``self.overlap`` tokens.

        Args:
            text: Text content to split.

        Returns:
            List of (chunk_text, token_count) tuples.
        """
        total_tokens = self._count_tokens(text)

        # If text already fits, return as single chunk
        if total_tokens <= self.token_limit:
            return [(text, total_tokens)]

        # Split on sentence boundaries — keep token counts alongside the text so
        # we never recount the same sentence twice.
        sentences = self.SENTENCE_PATTERN.split(text)
        sentence_tokens = [self._count_tokens(s) for s in sentences]

        upper = self.token_limit + self.tolerance
        lower = self.token_limit - self.tolerance

        chunks: list[tuple[str, int]] = []
        current_sentences: list[str] = []
        current_counts: list[int] = []
        current_tokens = 0
        # Tracks the size of the overlap prefix carried over from the previous
        # chunk so the final flush can skip emitting an overlap-only tail.
        overlap_prefix_len = 0

        for sentence, s_tokens in zip(sentences, sentence_tokens, strict=True):
            # Only finalise once the running chunk contains at least one
            # sentence beyond the overlap carried over from the previous chunk
            # — otherwise we'd emit a duplicate of the previous chunk's tail.
            has_new_content = len(current_sentences) > overlap_prefix_len
            # Hard cap: adding this sentence would overshoot ``limit + tolerance``.
            # Early-stop: running chunk already inside the ± band; finalise at
            # the previous sentence boundary rather than overshoot the target.
            if has_new_content and (current_tokens + s_tokens > upper or current_tokens >= lower):
                chunks.append((" ".join(current_sentences), current_tokens))
                (
                    current_sentences,
                    current_counts,
                    current_tokens,
                ) = self._build_overlap(current_sentences, current_counts)
                overlap_prefix_len = len(current_sentences)

            current_sentences.append(sentence)
            current_counts.append(s_tokens)
            current_tokens += s_tokens

        # Flush remaining sentences. Skip overlap-only tails — they would
        # duplicate the previous chunk entirely without contributing new text.
        if current_sentences and len(current_sentences) > overlap_prefix_len:
            chunks.append((" ".join(current_sentences), current_tokens))

        return chunks

    def _build_overlap(
        self,
        sentences: list[str],
        counts: list[int],
    ) -> tuple[list[str], list[int], int]:
        """
        Select trailing whole sentences from a just-finalised chunk to seed the
        next one. Walks backwards accumulating sentences while the total stays
        within ``self.overlap``. If even the single last sentence exceeds the
        budget, it is still reused whole — sentence boundaries are never split.
        """
        if self.overlap == 0 or not sentences:
            return [], [], 0

        overlap_sentences: list[str] = []
        overlap_counts: list[int] = []
        overlap_tokens = 0
        for sentence, s_tokens in zip(reversed(sentences), reversed(counts), strict=True):
            if overlap_sentences and overlap_tokens + s_tokens > self.overlap:
                break
            overlap_sentences.insert(0, sentence)
            overlap_counts.insert(0, s_tokens)
            overlap_tokens += s_tokens
            if overlap_tokens >= self.overlap:
                break

        return overlap_sentences, overlap_counts, overlap_tokens

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
                token_count=tokens,
            )
            for i, (text, tokens) in enumerate(text_chunks)
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

        # Log statistics — token counts are retained from chunking, no recount
        token_counts = [c.token_count for c in chunks]
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
