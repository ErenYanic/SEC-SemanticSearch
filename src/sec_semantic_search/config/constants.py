"""Application-wide constants."""

# Supported SEC filing forms
SUPPORTED_FORMS = ("10-K", "10-Q")

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
