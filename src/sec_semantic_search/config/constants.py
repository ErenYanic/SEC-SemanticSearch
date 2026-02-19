"""Application-wide constants."""

# Supported SEC filing forms
SUPPORTED_FORMS = ("10-K", "10-Q")

# Default form types for ingestion (both forms)
DEFAULT_FORM_TYPES = "10-K,10-Q"


def parse_form_types(form_input: str) -> tuple[str, ...]:
    """Parse and validate a comma-separated form type string.

    Accepts ``"10-K"``, ``"10-Q"``, ``"10-K,10-Q"``, ``"10-Q, 10-K"``, etc.
    Returns a sorted tuple of unique, validated form types.  Input order
    does not matter — ``"10-Q,10-K"`` produces the same result as
    ``"10-K,10-Q"``.

    Args:
        form_input: Comma-separated form type string.

    Returns:
        Sorted tuple of validated form types.

    Raises:
        ValueError: If any form type is not in ``SUPPORTED_FORMS``.
    """
    raw = [part.strip().upper() for part in form_input.split(",") if part.strip()]

    if not raw:
        raise ValueError(
            f"Empty form type. Supported: {', '.join(SUPPORTED_FORMS)}"
        )

    invalid = [f for f in raw if f not in SUPPORTED_FORMS]
    if invalid:
        raise ValueError(
            f"Unsupported form type(s): {', '.join(invalid)}. "
            f"Supported: {', '.join(SUPPORTED_FORMS)}"
        )

    return tuple(sorted(set(raw)))

# Embedding model parameters
EMBEDDING_DIMENSION = 768  # Dimension of google/embeddinggemma-300m
EMBEDDING_MODEL_NAME = "google/embeddinggemma-300m"

# Chunking parameters
DEFAULT_CHUNK_TOKEN_LIMIT = 500
DEFAULT_CHUNK_TOLERANCE = 50

# Database
DEFAULT_CHROMADB_PATH = "./data/chroma_db"
DEFAULT_METADATA_DB_PATH = "./data/metadata.sqlite"
DEFAULT_MAX_FILINGS = 20

# Collection naming
COLLECTION_NAME = "sec_filings"

# Search defaults
DEFAULT_SEARCH_TOP_K = 5
DEFAULT_MIN_SIMILARITY = 0.0
