"""
Pipeline module — fetch, parse, chunk, embed, and orchestrate.

This module provides the complete ingestion pipeline for SEC filings:
    - FilingFetcher: Fetch filings from SEC EDGAR
    - FilingParser: Parse HTML into semantic segments
    - TextChunker: Split segments into embedding-ready chunks
    - EmbeddingGenerator: Generate vector embeddings
    - PipelineOrchestrator: Coordinate the full pipeline

Usage:
    from sec_semantic_search.pipeline import (
        FilingFetcher,
        FilingParser,
        TextChunker,
        EmbeddingGenerator,
        PipelineOrchestrator,
    )

    # High-level usage with orchestrator
    orchestrator = PipelineOrchestrator()
    result = orchestrator.ingest_latest("AAPL", "10-K")

    # Low-level usage with individual components
    fetcher = FilingFetcher()
    filing_id, html = fetcher.fetch_latest("AAPL", "10-K")
"""

from sec_semantic_search.pipeline.chunk import TextChunker
from sec_semantic_search.pipeline.embed import EmbeddingGenerator
from sec_semantic_search.pipeline.fetch import FilingFetcher, FilingInfo
from sec_semantic_search.pipeline.orchestrator import (
    PipelineOrchestrator,
    ProcessedFiling,
    ProgressCallback,
)
from sec_semantic_search.pipeline.parse import FilingParser

__all__ = [
    # Main classes
    "FilingFetcher",
    "FilingParser",
    "TextChunker",
    "EmbeddingGenerator",
    "PipelineOrchestrator",
    # Supporting types
    "FilingInfo",
    "ProcessedFiling",
    "ProgressCallback",
]
