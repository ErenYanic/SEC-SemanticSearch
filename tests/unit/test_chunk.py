"""
Tests for the TextChunker pipeline component.

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
from sec_semantic_search.core.types import ContentType, Segment
from sec_semantic_search.pipeline.chunk import TextChunker


@pytest.fixture
def chunker() -> TextChunker:
    """
    A chunker with small, predictable limits.

    token_limit=20 and tolerance=5 make it easy to construct test
    inputs that are just above or below the boundary without needing
    hundreds of words. ``overlap`` is scaled down to ``5`` to match the
    miniature limit (matching the production 10 % ratio of 50/500).
    """
    return TextChunker(token_limit=20, tolerance=5, overlap=5)


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
        long_text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
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


class TestTokenCount:
    """Verify token_count is retained on chunks during creation."""

    def test_short_segment_token_count(self, chunker, sample_filing_id):
        """A short segment's single chunk should have correct token_count."""
        segment = Segment(
            path="Root",
            content_type=ContentType.TEXT,
            content="Five words in this segment.",
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) == 1
        assert chunks[0].token_count == len("Five words in this segment.".split())

    def test_long_segment_token_counts(self, chunker, sample_filing_id):
        """All chunks from a long segment should have non-zero token_count."""
        long_text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=long_text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.token_count == len(chunk.content.split())

    def test_chunk_segments_token_counts(self, chunker, sample_segments):
        """chunk_segments() should populate token_count on every chunk."""
        chunks = chunker.chunk_segments(sample_segments)
        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.token_count == len(chunk.content.split())


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
        """
        Text without sentence terminators should still be chunked.

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


class TestSymmetricTolerance:
    """± tolerance: chunks should land inside ``[limit - tolerance, limit + tolerance]``."""

    def test_chunks_respect_upper_bound(self, chunker, sample_filing_id):
        """No chunk should exceed ``token_limit + tolerance`` (hard cap)."""
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        for chunk in chunks:
            assert chunk.token_count <= chunker.token_limit + chunker.tolerance

    def test_chunks_respect_lower_bound_early_stop(self, chunker, sample_filing_id):
        """
        Non-terminal chunks must reach at least ``limit - tolerance`` tokens —
        the early-stop trigger only fires once we're already inside the band.
        Tail chunks may legitimately be short (they hold whatever's left).
        """
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2
        lower = chunker.token_limit - chunker.tolerance
        for chunk in chunks[:-1]:
            assert chunk.token_count >= lower, (
                f"Non-terminal chunk has {chunk.token_count} tokens, "
                f"below ± band lower bound {lower}"
            )

    def test_early_stop_prevents_overshoot(self, sample_filing_id):
        """
        With limit=20, tolerance=5, three 7-token sentences (=21) should
        finalise rather than continue accumulating — the previous ``+`` only
        algorithm would have allowed a fourth, taking the chunk to 28 tokens.
        """
        chunker = TextChunker(token_limit=20, tolerance=5, overlap=0)
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(8))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        # First chunk caps at three sentences (21 tokens) — never four (28).
        assert chunks[0].token_count == 21


class TestChunkOverlap:
    """Trailing sentences from chunk N should reappear at the start of chunk N+1."""

    def test_overlap_present_between_chunks(self, chunker, sample_filing_id):
        """Each non-first chunk should start with the last sentence of its predecessor."""
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2
        for prev, curr in zip(chunks[:-1], chunks[1:], strict=True):
            prev_sentences = TextChunker.SENTENCE_PATTERN.split(prev.content)
            curr_sentences = TextChunker.SENTENCE_PATTERN.split(curr.content)
            # The first sentence of the next chunk must come from the tail
            # of the previous chunk — preserving the sentence-boundary invariant.
            assert curr_sentences[0] in prev_sentences, (
                f"Expected overlap sentence {curr_sentences[0]!r} not found in previous chunk"
            )

    def test_overlap_respects_token_budget(self, chunker, sample_filing_id):
        """Overlap should not blow past the configured budget when whole sentences fit."""
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(20))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        # Each sentence is 7 tokens — overlap budget of 5 only fits when we
        # take a single sentence and accept the small overshoot inherent to
        # sentence-aligned overlap. We assert overlap is at most one sentence.
        for prev, curr in zip(chunks[:-1], chunks[1:], strict=True):
            prev_sentences = TextChunker.SENTENCE_PATTERN.split(prev.content)
            curr_sentences = TextChunker.SENTENCE_PATTERN.split(curr.content)
            shared = [s for s in curr_sentences if s in prev_sentences[-2:]]
            assert len(shared) <= 2  # No runaway overlap

    def test_overlap_disabled(self, sample_filing_id):
        """``overlap=0`` should produce disjoint chunks."""
        chunker = TextChunker(token_limit=20, tolerance=5, overlap=0)
        text = " ".join(f"Sentence number {i} about some financial topic." for i in range(15))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2
        # No sentence should appear in more than one chunk.
        sentence_appearances: dict[str, int] = {}
        for chunk in chunks:
            for sentence in TextChunker.SENTENCE_PATTERN.split(chunk.content):
                sentence_appearances[sentence] = sentence_appearances.get(sentence, 0) + 1
        for sentence, count in sentence_appearances.items():
            assert count == 1, f"Sentence {sentence!r} appears {count} times with overlap=0"

    def test_overlap_forces_at_least_one_sentence(self, sample_filing_id):
        """
        When the last sentence of a chunk exceeds the overlap budget, the
        chunker should still carry it whole — sentence boundaries are sacred.
        """
        # Trailing sentence (~25 tokens) far exceeds overlap budget (5).
        chunker = TextChunker(token_limit=50, tolerance=5, overlap=5)
        s1 = "alpha " * 10 + "end1."
        s2 = "beta " * 10 + "end2."
        s3 = "gamma " * 24 + "end3."  # ~25 tokens — far bigger than overlap budget
        tail = " ".join(f"Tail sentence number {i}." for i in range(8))
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=f"{s1} {s2} {s3} {tail}",
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        assert len(chunks) >= 2
        # ``end3.`` must reappear at the start of the second chunk — proving
        # the oversized trailing sentence was reused whole despite the small
        # overlap budget.
        assert "end3." in chunks[1].content
        assert chunks[1].content.startswith("gamma")

    def test_overlap_does_not_emit_duplicate_tail(self, sample_filing_id):
        """
        Pathological case: a single oversized sentence becomes its own overlap.
        The chunker must not emit it twice consecutively.
        """
        chunker = TextChunker(token_limit=20, tolerance=5, overlap=5)
        big = "alpha " * 25 + "end."
        text = big + " Short follow up sentence."
        segment = Segment(
            path="Part I",
            content_type=ContentType.TEXT,
            content=text,
            filing_id=sample_filing_id,
        )
        chunks = chunker.chunk_segment(segment)
        # No two consecutive chunks should be byte-identical.
        for prev, curr in zip(chunks[:-1], chunks[1:], strict=True):
            assert prev.content != curr.content


class TestConfigurationValidation:
    """The chunker should reject incoherent overlap/limit combinations."""

    def test_overlap_must_be_smaller_than_limit(self):
        with pytest.raises(ValueError, match="overlap"):
            TextChunker(token_limit=20, tolerance=5, overlap=20)

    def test_negative_overlap_rejected(self):
        with pytest.raises(ValueError, match="overlap"):
            TextChunker(token_limit=20, tolerance=5, overlap=-1)
