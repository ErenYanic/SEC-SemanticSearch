"""
Unit tests for EmbeddingGenerator GPU resource management.

Tests is_loaded, approximate_vram_mb, and unload() — the properties
used by the GPU resource endpoints (GET/DELETE /api/resources/gpu).
"""

from unittest.mock import MagicMock, patch

import numpy as np

from sec_semantic_search.config.constants import EMBEDDING_DIMENSION
from sec_semantic_search.pipeline.embed import EmbeddingGenerator


class TestIsLoaded:
    """is_loaded should reflect whether the model is in memory."""

    def test_false_initially(self):
        gen = EmbeddingGenerator()
        assert gen.is_loaded is False

    def test_true_after_model_set(self):
        gen = EmbeddingGenerator()
        gen._model = MagicMock()
        assert gen.is_loaded is True


class TestApproximateVramMb:
    """approximate_vram_mb should return None when not loaded."""

    def test_none_when_not_loaded(self):
        gen = EmbeddingGenerator()
        assert gen.approximate_vram_mb is None


class TestUnload:
    """unload() should clear the model reference."""

    def test_sets_model_to_none(self):
        gen = EmbeddingGenerator()
        gen._model = MagicMock()
        gen.unload()
        assert gen._model is None
        assert gen.is_loaded is False

    def test_unload_when_already_none(self):
        """Unloading when nothing is loaded should not raise."""
        gen = EmbeddingGenerator()
        gen.unload()  # Should not raise
        assert gen.is_loaded is False