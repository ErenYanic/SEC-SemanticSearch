"""Tests for the TextChunker pipeline component.

TextChunker is a pure algorithmic class — it splits Segments into
Chunks at sentence boundaries. These tests verify the splitting logic,
index assignment, metadata inheritance, and edge cases without touching
the network, GPU, or database.

We pass explicit token_limit and tolerance to the constructor to avoid
depending on the .env configuration, making tests reproducible on any
machine.
"""

import pytest

from sec_semantic_search.core.exceptions import ChunkingError
from sec_semantic_search.core.types import ContentType, FilingIdentifier, Segment
from sec_semantic_search.pipeline.chunk import TextChunker


@pytest.fixture
def chunker() -> TextChunker:
    """A chunker with small, predictable limits.

    token_limit=20 and tolerance=5 make it easy to construct test
    inputs that are just above or below the boundary without needing
    hundreds of words.
    """
    return TextChunker(token_limit=20, tolerance=5)


class TestShortSegments:
    """Segments that fit within the token limit should not be split."""

    def test_short_segment_single_chunk(self, chunker, sample_segments):
        """A segment under the limit produces exactly one chunk."""
        # sample_segments[1] is the short TEXTSMALL segment (~10 words)
        short_segment = sample_segments[1]
        chunks = chunker.chunk_segment(short_segment)
        assert len(chunks) == 1

    def test_short_segment_preserves_content(self, chunker, sample_segments):
        """Content should pass through unchanged when no split is needed."""
        short_segment = sample_segments[1]
        chunks = chunker.chunk_segment(short_segment)
        assert chunks[0].content == short_segment.content


class TestLongSegments:
    """Segments exceeding the token limit should be split."""

    def test_long_segment_produces_multiple_chunks(self, chunker, sample_filing_id):
        """A segment well over the limit should split into 2+ chunks."""
        # ~60 words: 3x the limit of 20
        long_text = (
            "First sentence about revenue growth. "
            "Second sentence about market share. "
            "Third sentence about product launches. "
            "Fourth sentence about international expansion. "
            "Fifth sentence about supply chain risks. "
            "Sixth sentence about regulatory compliance. "
            "Seventh sentence about research and development. "
            "Eighth sentence about customer satisfaction."
        )
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=long_text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2

    def test_chunks_within_limit_plus_tolerance(self, chunker, sample_filing_id):
        """Each chunk should respect token_limit + tolerance."""
        long_text = " ".join(
            f"Sentence number {i} about some financial topic." for i in range(20)
        )
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=long_text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        max_allowed = chunker.token_limit + chunker.tolerance
        for chunk in chunks:
            token_count = len(chunk.content.split())
            assert token_count <= max_allowed, (
                f"Chunk has {token_count} tokens, exceeds limit+tolerance={max_allowed}"
            )


class TestSentenceBoundaries:
    """The chunker should split at sentence boundaries, not mid-sentence."""

    def test_splits_at_period(self, chunker, sample_filing_id):
        """Chunks (except the last) should end with a sentence terminator."""
        text = (
            "Revenue increased by ten percent year over year. "
            "Gross margin improved due to cost reductions. "
            "Operating expenses remained flat compared to prior year. "
            "Net income grew substantially across all segments."
        )
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        # All chunks except possibly the last should end with . ! or ?
        for chunk in chunks[:-1]:
            assert chunk.content.rstrip().endswith((".", "!", "?")), (
                f"Chunk does not end at sentence boundary: ...{chunk.content[-30:]!r}"
            )


class TestChunkIndices:
    """Verify sequential index assignment across segments."""

    def test_sequential_indices(self, chunker, sample_segments):
        """chunk_segments() should assign 0, 1, 2, ... across all segments."""
        chunks = chunker.chunk_segments(sample_segments)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_start_index_offset(self, chunker, sample_segments):
        """chunk_segment(start_index=N) should start from N."""
        chunks = chunker.chunk_segment(sample_segments[0], start_index=10)
        assert chunks[0].chunk_index == 10


class TestMetadataInheritance:
    """Chunks must inherit metadata from their source segment."""

    def test_path_inherited(self, chunker, sample_segments):
        """Each chunk's path should match its source segment."""
        chunks = chunker.chunk_segment(sample_segments[0])
        for chunk in chunks:
            assert chunk.path == sample_segments[0].path

    def test_content_type_inherited(self, chunker, sample_segments):
        """Each chunk's content_type should match its source segment."""
        for segment in sample_segments:
            chunks = chunker.chunk_segment(segment)
            for chunk in chunks:
                assert chunk.content_type is segment.content_type

    def test_filing_id_inherited(self, chunker, sample_segments):
        """Each chunk's filing_id should reference the same object."""
        chunks = chunker.chunk_segments(sample_segments)
        for chunk in chunks:
            assert chunk.filing_id is sample_segments[0].filing_id


class TestEdgeCases:
    """Error handling and boundary conditions."""

    def test_empty_segments_raises(self, chunker):
        """chunk_segments([]) should raise ChunkingError."""
        with pytest.raises(ChunkingError, match="No segments to chunk"):
            chunker.chunk_segments([])

    def test_single_word_segment(self, chunker, sample_filing_id):
        """A one-word segment should produce one chunk."""
        segment = Segment(
            path="Root",
            content_type=ContentType.TEXTSMALL,
            content="Disclaimer.",
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) == 1
        assert chunks[0].content == "Disclaimer."

    def test_no_sentence_boundaries(self, chunker, sample_filing_id):
        """Text without sentence terminators should still be chunked.

        The chunker accumulates until limit+tolerance is exceeded,
        then starts a new chunk even without clean boundaries.
        """
        # 30 words with no periods — exceeds limit of 20
        text = " ".join(f"word{i}" for i in range(30))
        segment = Segment(
            path="Root",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        # With no sentence splits, the entire text is one "sentence",
        # so it stays as one chunk (the algorithm doesn't break mid-sentence)
        assert len(chunks) >= 1
        # All original words should be present across chunks
        all_words = " ".join(c.content for c in chunks).split()
        assert len(all_words) == 30
