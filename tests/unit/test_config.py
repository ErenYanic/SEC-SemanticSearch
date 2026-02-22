"""Tests for configuration management and constants.

The settings module was the site of two Pydantic v2 bugs (extra="ignore"
and load_dotenv before nested defaults). These tests serve as regression
guards. We also verify the singleton pattern, default values, and that
constants used by other modules have the expected values.
"""

import sec_semantic_search.config.settings as settings_module
from sec_semantic_search.config.constants import (
    COLLECTION_NAME,
    DEFAULT_CHUNK_TOKEN_LIMIT,
    DEFAULT_CHUNK_TOLERANCE,
    DEFAULT_MAX_FILINGS,
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_SEARCH_TOP_K,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    SUPPORTED_FORMS,
)
from sec_semantic_search.config.settings import (
    ChunkingSettings,
    DatabaseSettings,
    EmbeddingSettings,
    HuggingFaceSettings,
    SearchSettings,
    Settings,
    get_settings,
    reload_settings,
)


# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------


class TestConstants:
    """Verify critical constants that other modules depend on."""

    def test_supported_forms(self):
        """SUPPORTED_FORMS must include both 10-K and 10-Q."""
        assert "10-K" in SUPPORTED_FORMS
        assert "10-Q" in SUPPORTED_FORMS

    def test_embedding_dimension(self):
        """Must match google/embeddinggemma-300m's output dimension."""
        assert EMBEDDING_DIMENSION == 768

    def test_embedding_model_name(self):
        assert EMBEDDING_MODEL_NAME == "google/embeddinggemma-300m"

    def test_collection_name(self):
        assert COLLECTION_NAME == "sec_filings"

    def test_default_chunk_limits(self):
        assert DEFAULT_CHUNK_TOKEN_LIMIT == 500
        assert DEFAULT_CHUNK_TOLERANCE == 50

    def test_default_search_values(self):
        assert DEFAULT_SEARCH_TOP_K == 5
        assert DEFAULT_MIN_SIMILARITY == 0.0

    def test_default_max_filings(self):
        assert DEFAULT_MAX_FILINGS == 100


# -----------------------------------------------------------------------
# Nested settings defaults
# -----------------------------------------------------------------------


class TestSettingsDefaults:
    """Nested settings classes should have sensible defaults."""

    def test_embedding_defaults(self, monkeypatch):
        """Code defaults should apply when env vars are absent."""
        monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)
        monkeypatch.delenv("EMBEDDING_DEVICE", raising=False)
        monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
        s = EmbeddingSettings()
        assert s.model_name == "google/embeddinggemma-300m"
        assert s.device == "auto"
        assert s.batch_size == 32

    def test_chunking_defaults(self):
        s = ChunkingSettings()
        assert s.token_limit == 500
        assert s.tolerance == 50

    def test_database_defaults(self):
        s = DatabaseSettings()
        assert s.chroma_path == "./data/chroma_db"
        assert s.metadata_db_path == "./data/metadata.sqlite"
        assert s.max_filings == 100

    def test_search_defaults(self):
        s = SearchSettings()
        assert s.top_k == 5
        assert s.min_similarity == 0.0

    def test_hugging_face_defaults(self, monkeypatch):
        """Token should be None when no env var is set."""
        monkeypatch.delenv("HUGGING_FACE_TOKEN", raising=False)
        s = HuggingFaceSettings()
        assert s.token is None


# -----------------------------------------------------------------------
# Root Settings and singleton
# -----------------------------------------------------------------------


class TestRootSettings:
    """The root Settings class composes all nested settings."""

    def test_has_all_sections(self):
        s = Settings()
        assert hasattr(s, "edgar")
        assert hasattr(s, "embedding")
        assert hasattr(s, "chunking")
        assert hasattr(s, "database")
        assert hasattr(s, "search")
        assert hasattr(s, "hugging_face")

    def test_extra_ignore(self):
        """The extra='ignore' setting must be present to avoid rejecting
        prefixed env vars that belong to nested classes (regression test
        for Pydantic bug #1).
        """
        assert Settings.model_config.get("extra") == "ignore"


class TestSingleton:
    """get_settings() should return the same instance on repeated calls."""

    def test_get_settings_returns_settings(self):
        s = get_settings()
        assert isinstance(s, Settings)

    def test_get_settings_is_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload_settings_returns_new_instance(self):
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2

    def test_reload_updates_global(self):
        """After reload, get_settings() should return the new instance."""
        s_old = get_settings()
        s_new = reload_settings()
        assert get_settings() is s_new
        assert get_settings() is not s_old
        # Restore original to avoid side effects on other tests
        settings_module._settings_instance = s_old
