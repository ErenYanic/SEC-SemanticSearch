"""Configuration management using Pydantic Settings v2."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ BEFORE nested BaseSettings classes are
# instantiated as default values in the Settings class body.  Without
# this, EdgarSettings() (which has required fields and no defaults)
# fails because it only searches os.environ — it has no env_file of
# its own.
load_dotenv()


class EdgarSettings(BaseSettings):
    """SEC EDGAR API credentials."""

    identity_name: str
    identity_email: str

    model_config = SettingsConfigDict(env_prefix="EDGAR_")


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""

    model_name: str = "all-MiniLM-L6-v2"
    device: str = "auto"  # "cuda", "cpu", or "auto"
    batch_size: int = 32

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")


class ChunkingSettings(BaseSettings):
    """Text chunking configuration."""

    token_limit: int = 500
    tolerance: int = 50

    model_config = SettingsConfigDict(env_prefix="CHUNKING_")


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    chroma_path: str = "./data/chroma_db"
    metadata_db_path: str = "./data/metadata.sqlite"
    max_filings: int = 20

    model_config = SettingsConfigDict(env_prefix="DB_")


class SearchSettings(BaseSettings):
    """Search configuration."""

    top_k: int = 5
    min_similarity: float = 0.0

    model_config = SettingsConfigDict(env_prefix="SEARCH_")


class HuggingFaceSettings(BaseSettings):
    """Hugging Face configuration."""

    token: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="HUGGING_FACE_")


class Settings(BaseSettings):
    """Root settings class combining all sections."""

    edgar: EdgarSettings = EdgarSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    chunking: ChunkingSettings = ChunkingSettings()
    database: DatabaseSettings = DatabaseSettings()
    search: SearchSettings = SearchSettings()
    hugging_face: HuggingFaceSettings = HuggingFaceSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore prefixed env vars handled by nested classes
    )


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global Settings instance (singleton pattern)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Reload settings from environment (mainly for testing)."""
    global _settings_instance
    _settings_instance = Settings()
    return _settings_instance
