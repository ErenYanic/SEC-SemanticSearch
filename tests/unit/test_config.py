"""Tests for configuration management and constants.

The settings module was the site of two Pydantic v2 bugs (extra="ignore"
and load_dotenv before nested defaults). These tests serve as regression
guards. We also verify the singleton pattern, default values, and that
constants used by other modules have the expected values.
"""

import pytest

import sec_semantic_search.config.settings as settings_module
from sec_semantic_search.config.constants import (
    COLLECTION_NAME,
    DEFAULT_CHUNK_TOKEN_LIMIT,
    DEFAULT_CHUNK_TOLERANCE,
    DEFAULT_FORM_TYPES,
    DEFAULT_MAX_FILINGS,
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_SEARCH_TOP_K,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    SUPPORTED_FORMS,
    parse_form_types,
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

    def test_default_form_types_value(self):
        """DEFAULT_FORM_TYPES must list both supported forms."""
        assert DEFAULT_FORM_TYPES == "10-K,10-Q"

    def test_default_form_types_roundtrip(self):
        """DEFAULT_FORM_TYPES must be compatible with parse_form_types()."""
        assert parse_form_types(DEFAULT_FORM_TYPES) == ("10-K", "10-Q")


# -----------------------------------------------------------------------
# parse_form_types()
# -----------------------------------------------------------------------


class TestParseFormTypes:
    """parse_form_types() validates, normalises, deduplicates, and sorts."""

    def test_single_valid_form(self):
        assert parse_form_types("10-K") == ("10-K",)

    def test_both_forms(self):
        assert parse_form_types("10-K,10-Q") == ("10-K", "10-Q")

    def test_order_independence(self):
        """Input order should not affect the output."""
        assert parse_form_types("10-Q,10-K") == ("10-K", "10-Q")

    def test_case_insensitivity(self):
        assert parse_form_types("10-k") == ("10-K",)

    def test_whitespace_handling(self):
        assert parse_form_types("10-K , 10-Q") == ("10-K", "10-Q")

    def test_deduplication(self):
        assert parse_form_types("10-K,10-K") == ("10-K",)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty form type"):
            parse_form_types("")

    def test_invalid_form_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            parse_form_types("8-K")

    def test_mixed_valid_invalid_raises(self):
        """Even one invalid form in a comma-separated list should fail."""
        with pytest.raises(ValueError, match="Unsupported"):
            parse_form_types("10-K,8-K")


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

    def test_has_all_sections(self, monkeypatch):
        """Root Settings composes all nested settings sections.

        monkeypatch sets EDGAR credentials so the test does not depend
        on a real .env file.
        """
        monkeypatch.setenv("EDGAR_IDENTITY_NAME", "Test User")
        monkeypatch.setenv("EDGAR_IDENTITY_EMAIL", "test@example.com")
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
