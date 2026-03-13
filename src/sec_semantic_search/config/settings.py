"""Configuration management using Pydantic Settings v2."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import model_validator
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

    model_name: str = "google/embeddinggemma-300m"
    device: str = "auto"  # "cuda", "cpu", or "auto"
    batch_size: int = 32
    idle_timeout_minutes: int = 0  # 0 = disabled; auto-unload model after idle

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
    max_filings: int = 500

    model_config = SettingsConfigDict(env_prefix="DB_")

    @model_validator(mode="after")
    def _validate_paths(self) -> "DatabaseSettings":
        """Validate that database paths resolve within the working directory.

        Prevents path traversal attacks where an attacker controls environment
        variables (e.g. ``DB_METADATA_DB_PATH=../../sensitive/data.sqlite``)
        to write files outside the project directory.

        Checks:
        - Resolved path must be relative to ``Path.cwd()``
        - No symlinks in parent directories (prevents symlink-based escapes)
        """
        base_dir = Path.cwd().resolve()
        for field_name in ("chroma_path", "metadata_db_path"):
            raw_value = getattr(self, field_name)
            resolved = Path(raw_value).resolve()

            # Check the path stays within the working directory
            if not resolved.is_relative_to(base_dir):
                raise ValueError(
                    f"Database path '{field_name}' resolves to "
                    f"'{resolved}' which is outside the project "
                    f"directory '{base_dir}'. Use a relative path "
                    f"within the project directory."
                )

            # Check for symlinks in existing parent directories
            # (prevents symlink-based directory escapes)
            check = resolved
            while check != base_dir:
                if check.is_symlink():
                    raise ValueError(
                        f"Database path '{field_name}' contains a "
                        f"symlink at '{check}'. Symlinks are not "
                        f"permitted in database paths for security."
                    )
                check = check.parent

        return self


class SearchSettings(BaseSettings):
    """Search configuration."""

    top_k: int = 5
    min_similarity: float = 0.0

    model_config = SettingsConfigDict(env_prefix="SEARCH_")


class HuggingFaceSettings(BaseSettings):
    """Hugging Face configuration."""

    token: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix="HUGGING_FACE_")


class ApiSettings(BaseSettings):
    """API server configuration."""

    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    key: Optional[str] = None  # API key; None = auth disabled (local dev)

    # Rate limiting (requests per minute; 0 = disabled)
    rate_limit_search: int = 60
    rate_limit_ingest: int = 10
    rate_limit_delete: int = 30
    rate_limit_general: int = 120

    model_config = SettingsConfigDict(env_prefix="API_")


class Settings(BaseSettings):
    """Root settings class combining all sections."""

    edgar: EdgarSettings = EdgarSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    chunking: ChunkingSettings = ChunkingSettings()
    database: DatabaseSettings = DatabaseSettings()
    search: SearchSettings = SearchSettings()
    hugging_face: HuggingFaceSettings = HuggingFaceSettings()
    api: ApiSettings = ApiSettings()

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
