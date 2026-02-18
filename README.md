# SEC-SemanticSearch

A **semantic search system** for SEC filings (10-K, 10-Q). Fetches filings from EDGAR, parses them into meaningful segments, embeds them with a local GPU-accelerated model, and retrieves the most relevant passages for any natural language query.

This is a classic **vector similarity search** system — not RAG. There is no language model generating answers; the system returns the actual filing text that best matches your query.

## Features

- **Full pipeline** — Fetch, parse, chunk, embed, and store SEC filings in one command
- **GPU-accelerated embeddings** — Uses `google/embeddinggemma-300m` (768-dim) via sentence-transformers with CUDA support
- **Dual-store architecture** — ChromaDB for vector similarity search, SQLite for relational metadata
- **Rich CLI** — Progress bars, colour-coded output, formatted tables, contextual error hints
- **Web interface** — Multi-page Streamlit UI with dashboard, search, ingestion, and filing management
- **Flexible filtering** — Search by ticker, form type, or both
- **Duplicate detection** — Prevents re-ingesting filings already stored
- **Configurable** — All settings tuneable via environment variables

## Requirements

- Python 3.13+
- NVIDIA GPU with CUDA support (recommended; CPU fallback available)
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

## Installation

```bash
# Clone the repository
git clone https://github.com/ErenYanic/SEC-SemanticSearch.git
cd SEC-SemanticSearch

# Create and activate a virtual environment
uv venv uv_SEC_SemanticSearch
source uv_SEC_SemanticSearch/bin/activate

# Install in development mode
uv pip install -e ".[dev]"
```

### Configuration

Copy the example environment file and fill in your SEC EDGAR credentials:

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description |
|----------|-------------|
| `EDGAR_IDENTITY_NAME` | Your name (SEC EDGAR requires identification) |
| `EDGAR_IDENTITY_EMAIL` | Your email address |

**Optional variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `HUGGING_FACE_TOKEN` | — | HF token for faster model downloads |
| `EMBEDDING_MODEL_NAME` | `google/embeddinggemma-300m` | Sentence-transformer model |
| `EMBEDDING_DEVICE` | `auto` | `cuda`, `cpu`, or `auto` |
| `EMBEDDING_BATCH_SIZE` | `32` | Reduce for low-VRAM GPUs (e.g. `8`) |
| `CHUNKING_TOKEN_LIMIT` | `500` | Maximum tokens per chunk |
| `DB_CHROMA_PATH` | `./data/chroma_db` | ChromaDB storage path |
| `DB_METADATA_DB_PATH` | `./data/metadata.sqlite` | SQLite metadata path |
| `DB_MAX_FILINGS` | `20` | Maximum filings to store |
| `SEARCH_TOP_K` | `5` | Default number of search results |
| `SEARCH_MIN_SIMILARITY` | `0.0` | Minimum similarity threshold |

See [`.env.example`](.env.example) for the full list with descriptions.

## Usage

The project provides two interfaces: a CLI (`sec-search`) and a web UI (`sec-search-web`).

### CLI Commands

The CLI is accessed via the `sec-search` command (or `python -m sec_semantic_search`).

#### Ingest filings

```bash
# Ingest the latest 10-K filing for Apple
sec-search ingest add AAPL

# Ingest a 10-Q filing instead
sec-search ingest add AAPL --form 10-Q

# Batch ingest multiple companies
sec-search ingest batch AAPL MSFT GOOGL
```

#### Search filings

```bash
# Basic semantic search
sec-search search "risk factors related to supply chain"

# Limit results and filter by ticker
sec-search search "revenue recognition" --top 10 --ticker AAPL

# Filter by form type
sec-search search "liquidity" --form 10-Q
```

#### Manage the database

```bash
# View database status (filing count, chunk count, tickers)
sec-search manage status

# List all ingested filings
sec-search manage list

# List filings filtered by ticker
sec-search manage list --ticker AAPL

# Remove a filing by accession number
sec-search manage remove 0000320193-24-000123

# Skip confirmation prompt
sec-search manage remove 0000320193-24-000123 --yes
```

#### Other options

```bash
# Show version
sec-search --version

# Enable verbose debug output
sec-search --verbose ingest add AAPL
```

### Web Interface

Launch the Streamlit web interface:

```bash
# Via console script
sec-search-web

# Or via Streamlit directly
streamlit run src/sec_semantic_search/web/app.py
```

The web UI is a multi-page application with four pages:

- **Dashboard** — Overview of ingested filings with key metrics (filing count with capacity, chunk count, unique tickers), a form type bar chart, and a per-ticker breakdown table
- **Search** — Semantic search with sidebar filters (ticker, form type, result count), colour-coded similarity scores, and bordered result cards
- **Ingest** — Fetch and store filings with a form-based input, step-by-step progress display, and success metrics
- **Filings** — View and manage ingested filings with inline filters and a confirmation dialog for deletion

### Python API

The package can also be used programmatically. Below are examples covering common workflows.

#### End-to-end: ingest and search

```python
from sec_semantic_search.pipeline import PipelineOrchestrator
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.search import SearchEngine

# 1. Process a filing (fetch → parse → chunk → embed)
orchestrator = PipelineOrchestrator()
result = orchestrator.ingest_latest("AAPL", "10-K")

print(f"Segments: {result.ingest_result.segment_count}")
print(f"Chunks:   {result.ingest_result.chunk_count}")
print(f"Time:     {result.ingest_result.duration_seconds:.1f}s")

# 2. Store in both databases (ChromaDB first, then SQLite)
chroma = ChromaDBClient()
chroma.store_filing(result)

registry = MetadataRegistry()
registry.register_filing(result.filing_id, result.ingest_result.chunk_count)

# 3. Search across all stored filings
engine = SearchEngine()
results = engine.search("risk factors related to supply chain")

for r in results:
    print(f"{r.similarity:.1%} — {r.ticker} {r.form_type} — {r.section_path}")
    print(r.content[:200])
    print()
```

#### Search with filters

```python
from sec_semantic_search.search import SearchEngine

engine = SearchEngine()

# Filter by ticker and form type
results = engine.search(
    "revenue recognition policies",
    top_k=10,
    ticker="MSFT",
    form_type="10-K",
    min_similarity=0.25,
)
```

#### Using individual pipeline stages

```python
from sec_semantic_search.pipeline.fetch import FilingFetcher
from sec_semantic_search.pipeline import FilingParser, TextChunker

# Fetch without processing
fetcher = FilingFetcher()
filing_id, html = fetcher.fetch_latest("GOOGL", "10-Q")

# Parse HTML into segments
parser = FilingParser()
segments = parser.parse(filing_id, html)
print(f"Extracted {len(segments)} segments")

# Chunk segments for embedding
chunker = TextChunker()
chunks = chunker.chunk_segments(segments)
print(f"Produced {len(chunks)} chunks")
```

#### Database management

```python
from sec_semantic_search.database import MetadataRegistry, ChromaDBClient

registry = MetadataRegistry()
chroma = ChromaDBClient()

# List stored filings
for record in registry.list_filings(ticker="AAPL"):
    print(f"{record.ticker} {record.form_type} — {record.filing_date}")

# Check counts
print(f"Filings: {registry.count()}")
print(f"Chunks:  {chroma.collection_count()}")

# Remove a filing from both stores
accession = "0000320193-24-000123"
deleted = chroma.delete_filing(accession)
registry.remove_filing(accession)
print(f"Removed {deleted} chunks")
```

## Pipeline

```
Fetch (edgartools) → Parse (doc2dict) → Chunk (regex) → Embed (sentence-transformers) → Store (ChromaDB + SQLite)
     ↓                     ↓                 ↓                    ↓
FilingIdentifier      list[Segment]     list[Chunk]          np.ndarray
+ HTML content        with paths        with indices         (n, 768)
```

**Search:** Query → Embed → ChromaDB cosine similarity → Ranked results with similarity scores

## Project Structure

```
SEC-SemanticSearch/
├── pyproject.toml                    # Package config, dependencies, CLI entry points
├── .env.example                      # Environment variable template
├── src/sec_semantic_search/
│   ├── config/                       # Settings (Pydantic) and constants
│   ├── core/                         # Types, exceptions, logging
│   ├── pipeline/                     # Fetch, parse, chunk, embed, orchestrate
│   ├── database/                     # ChromaDB client, SQLite metadata registry
│   ├── search/                       # SearchEngine facade
│   ├── cli/                          # Typer CLI (ingest, search, manage)
│   └── web/                          # Streamlit interface (multi-page)
│       ├── app.py                    # Entrypoint — page config and navigation
│       ├── _shared.py                # Cached resource singletons
│       ├── run.py                    # Launch helper for sec-search-web
│       └── pages/                    # Dashboard, search, ingest, filings
├── tests/
│   ├── unit/                         # 169 unit tests
│   └── integration/                  # 42 integration tests
├── notebooks/
│   └── sec_semantic_search.ipynb     # Original working prototype
└── data/                             # Runtime data (gitignored)
    ├── chroma_db/                    # Vector database
    └── metadata.sqlite               # Filing registry
```

## Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run only unit tests
python -m pytest tests/unit/

# Run only integration tests
python -m pytest tests/integration/
```

211 tests (169 unit + 42 integration), all passing in ~8 seconds.

## Technology Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| Filing retrieval | [edgartools](https://github.com/dgunning/edgartools) | SEC EDGAR API wrapper |
| HTML parsing | [doc2dict](https://github.com/peterbe/doc2dict) | Structured document extraction |
| Embeddings | [sentence-transformers](https://sbert.net/) | `google/embeddinggemma-300m` (768-dim) |
| Vector database | [ChromaDB](https://www.trychroma.com/) | Persistent local storage, cosine similarity |
| Web interface | [Streamlit](https://streamlit.io/) | Multi-page UI with cached GPU resources |
| CLI | [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) | Modern CLI with formatted output |
| Configuration | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Environment-based config management |

## Licence

MIT
