"""Configuration module — settings and constants."""

from sec_semantic_search.config.constants import (
    COLLECTION_NAME,
    DEFAULT_CHUNK_TOLERANCE,
    DEFAULT_CHUNK_TOKEN_LIMIT,
    DEFAULT_CHROMADB_PATH,
    DEFAULT_FORM_TYPES,
    DEFAULT_MAX_FILINGS,
    DEFAULT_METADATA_DB_PATH,
    DEFAULT_MIN_SIMILARITY,
    DEFAULT_SEARCH_TOP_K,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    SUPPORTED_FORMS,
    parse_form_types,
)
from sec_semantic_search.config.settings import (
    ApiSettings,
    ChunkingSettings,
    DatabaseSettings,
    EdgarSettings,
    EmbeddingSettings,
    HuggingFaceSettings,
    SearchSettings,
    Settings,
    get_settings,
    reload_settings,
)

__all__ = [
    # Constants
    "SUPPORTED_FORMS",
    "DEFAULT_FORM_TYPES",
    "parse_form_types",
    "EMBEDDING_DIMENSION",
    "EMBEDDING_MODEL_NAME",
    "DEFAULT_CHUNK_TOKEN_LIMIT",
    "DEFAULT_CHUNK_TOLERANCE",
    "DEFAULT_CHROMADB_PATH",
    "DEFAULT_METADATA_DB_PATH",
    "DEFAULT_MAX_FILINGS",
    "COLLECTION_NAME",
    "DEFAULT_SEARCH_TOP_K",
    "DEFAULT_MIN_SIMILARITY",
    # Settings
    "ApiSettings",
    "Settings",
    "EdgarSettings",
    "EmbeddingSettings",
    "ChunkingSettings",
    "DatabaseSettings",
    "SearchSettings",
    "HuggingFaceSettings",
    "get_settings",
    "reload_settings",
]
