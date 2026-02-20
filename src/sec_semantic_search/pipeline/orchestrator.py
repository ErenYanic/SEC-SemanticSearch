"""
Pipeline orchestrator for SEC filing ingestion.

This module coordinates the full ingestion pipeline:
    Fetch → Parse → Chunk → Embed

It provides a unified interface for processing SEC filings,
handling both single-filing and batch operations.

Usage:
    from sec_semantic_search.pipeline import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()

    # Process a single filing
    result = orchestrator.process_filing(filing_id, html_content)

    # Ingest latest filing for a company
    result = orchestrator.ingest_latest("AAPL", "10-K")

    # Batch ingest multiple companies
    for result in orchestrator.ingest_batch(["AAPL", "MSFT"], "10-K"):
        print(f"Ingested {result.filing_id.ticker}")
"""

import time
from dataclasses import dataclass
from typing import Callable, Iterator

import numpy as np

from sec_semantic_search.core import (
    Chunk,
    FilingIdentifier,
    IngestResult,
    Segment,
    get_logger,
)
from sec_semantic_search.pipeline.chunk import TextChunker
from sec_semantic_search.pipeline.embed import EmbeddingGenerator
from sec_semantic_search.pipeline.fetch import FilingFetcher
from sec_semantic_search.pipeline.parse import FilingParser

logger = get_logger(__name__)


# Type alias for progress callback
ProgressCallback = Callable[[str, int, int], None]


@dataclass
class ProcessedFiling:
    """
    Result of processing a single filing through the pipeline.

    This contains all the data needed for storage in the database.

    Attributes:
        filing_id: Identifier for the filing
        segments: Extracted segments from parsing
        chunks: Chunked text ready for storage
        embeddings: Vector embeddings for each chunk
        ingest_result: Statistics about the ingestion
    """

    filing_id: FilingIdentifier
    segments: list[Segment]
    chunks: list[Chunk]
    embeddings: np.ndarray
    ingest_result: IngestResult


class PipelineOrchestrator:
    """
    Coordinates the SEC filing ingestion pipeline.

    This class ties together the fetcher, parser, chunker, and embedding
    generator to provide a unified interface for processing filings.

    The orchestrator handles:
        - Single filing processing (when HTML is already available)
        - Single company ingestion (fetch + process)
        - Batch ingestion (multiple companies/filings)
        - Progress reporting via callbacks

    Note:
        The orchestrator does NOT handle database storage. It returns
        ProcessedFiling objects containing chunks and embeddings that
        the database layer can store.

    Example:
        >>> orchestrator = PipelineOrchestrator()
        >>> result = orchestrator.ingest_latest("AAPL", "10-K")
        >>> print(f"Processed {result.ingest_result.chunk_count} chunks")
    """

    def __init__(
        self,
        fetcher: FilingFetcher | None = None,
        parser: FilingParser | None = None,
        chunker: TextChunker | None = None,
        embedder: EmbeddingGenerator | None = None,
    ) -> None:
        """
        Initialise the orchestrator with pipeline components.

        Components are created with defaults if not provided, allowing
        dependency injection for testing.

        Args:
            fetcher: FilingFetcher instance (optional)
            parser: FilingParser instance (optional)
            chunker: TextChunker instance (optional)
            embedder: EmbeddingGenerator instance (optional)
        """
        self.fetcher = fetcher or FilingFetcher()
        self.parser = parser or FilingParser()
        self.chunker = chunker or TextChunker()
        self.embedder = embedder or EmbeddingGenerator()

        logger.debug("PipelineOrchestrator initialised")

    def process_filing(
        self,
        filing_id: FilingIdentifier,
        html_content: str,
        progress_callback: ProgressCallback | None = None,
    ) -> ProcessedFiling:
        """
        Process a single filing through the pipeline.

        This method runs the full pipeline on HTML content that has
        already been fetched. Use this when you have the HTML content
        available (e.g., from a previous fetch or cache).

        Pipeline steps:
            1. Parse HTML → Segments
            2. Chunk segments → Chunks
            3. Generate embeddings

        Args:
            filing_id: Identifier for the filing
            html_content: Raw HTML content
            progress_callback: Optional callback(step_name, current, total)

        Returns:
            ProcessedFiling containing all processed data

        Example:
            >>> result = orchestrator.process_filing(filing_id, html)
            >>> print(f"Created {len(result.chunks)} chunks")
        """
        start_time = time.time()

        def report_progress(step: str, current: int, total: int) -> None:
            if progress_callback:
                progress_callback(step, current, total)

        logger.info(
            "Processing %s %s (%s)",
            filing_id.ticker,
            filing_id.form_type,
            filing_id.date_str,
        )

        # Step 1: Parse
        report_progress("Parsing", 1, 4)
        segments = self.parser.parse(html_content, filing_id)

        # Step 2: Chunk
        report_progress("Chunking", 2, 4)
        chunks = self.chunker.chunk_segments(segments)

        # Step 3: Embed
        report_progress("Embedding", 3, 4)
        embeddings = self.embedder.embed_chunks(chunks, show_progress=False)

        # Complete
        report_progress("Complete", 4, 4)
        duration = time.time() - start_time

        ingest_result = IngestResult(
            filing_id=filing_id,
            segment_count=len(segments),
            chunk_count=len(chunks),
            duration_seconds=duration,
        )

        logger.info(
            "Processed %s %s: %d segments → %d chunks in %.1fs",
            filing_id.ticker,
            filing_id.form_type,
            len(segments),
            len(chunks),
            duration,
        )

        return ProcessedFiling(
            filing_id=filing_id,
            segments=segments,
            chunks=chunks,
            embeddings=embeddings,
            ingest_result=ingest_result,
        )

    def ingest_latest(
        self,
        ticker: str,
        form_type: str = "10-K",
        progress_callback: ProgressCallback | None = None,
    ) -> ProcessedFiling:
        """
        Fetch and process the latest filing for a company.

        This is a convenience method that combines fetching and processing
        for the most recent filing of the specified type.

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type ("10-K" or "10-Q")
            progress_callback: Optional callback(step_name, current, total)

        Returns:
            ProcessedFiling containing all processed data

        Example:
            >>> result = orchestrator.ingest_latest("AAPL", "10-K")
            >>> print(f"Ingested: {result.filing_id.date_str}")
        """
        logger.info("Ingesting latest %s for %s", form_type, ticker)

        # Fetch
        if progress_callback:
            progress_callback("Fetching", 0, 4)

        filing_id, html_content = self.fetcher.fetch_latest(ticker, form_type)

        # Process
        return self.process_filing(filing_id, html_content, progress_callback)

    def ingest_one(
        self,
        ticker: str,
        form_type: str = "10-K",
        *,
        index: int = 0,
        year: int | list[int] | range | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ProcessedFiling:
        """
        Fetch and process a specific filing by index.

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type ("10-K" or "10-Q")
            index: Position in results (0=most recent)
            year: Optional year filter
            progress_callback: Optional callback

        Returns:
            ProcessedFiling containing all processed data
        """
        logger.info(
            "Ingesting %s %s at index %d",
            ticker,
            form_type,
            index,
        )

        if progress_callback:
            progress_callback("Fetching", 0, 4)

        filing_id, html_content = self.fetcher.fetch_one(
            ticker, form_type, index=index, year=year
        )

        return self.process_filing(filing_id, html_content, progress_callback)

    def ingest_multiple(
        self,
        ticker: str,
        form_type: str = "10-K",
        *,
        count: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterator[ProcessedFiling]:
        """
        Fetch and process multiple filings for a company.

        This method yields ProcessedFiling objects one at a time,
        allowing incremental processing and storage.

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type
            count: Maximum number of filings
            year: Year filter
            start_date: Date range start
            end_date: Date range end

        Yields:
            ProcessedFiling for each successfully processed filing

        Example:
            >>> for result in orchestrator.ingest_multiple("AAPL", count=5):
            ...     print(f"Processed: {result.filing_id.date_str}")
        """
        logger.info(
            "Ingesting multiple %s filings for %s",
            form_type,
            ticker,
        )

        for filing_id, html_content in self.fetcher.fetch(
            ticker,
            form_type,
            count=count,
            year=year,
            start_date=start_date,
            end_date=end_date,
        ):
            try:
                yield self.process_filing(filing_id, html_content)
            except Exception as e:
                logger.warning(
                    "Failed to process %s: %s",
                    filing_id.accession_number,
                    str(e),
                )
                continue

    def ingest_batch(
        self,
        tickers: list[str],
        form_type: str = "10-K",
        *,
        count_per_ticker: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Iterator[ProcessedFiling]:
        """
        Fetch and process filings for multiple companies.

        This method yields ProcessedFiling objects for each successfully
        processed filing across all specified tickers.

        Args:
            tickers: List of stock ticker symbols
            form_type: SEC form type
            count_per_ticker: Max filings per company
            year: Year filter
            start_date: Date range start
            end_date: Date range end

        Yields:
            ProcessedFiling for each successfully processed filing

        Example:
            >>> tickers = ["AAPL", "MSFT", "GOOGL"]
            >>> for result in orchestrator.ingest_batch(tickers, "10-K", year=2024):
            ...     print(f"Processed: {result.filing_id.ticker}")
        """
        logger.info(
            "Batch ingesting %s filings for %d companies",
            form_type,
            len(tickers),
        )

        for filing_id, html_content in self.fetcher.fetch_batch(
            tickers,
            form_type,
            count_per_ticker=count_per_ticker,
            year=year,
            start_date=start_date,
            end_date=end_date,
        ):
            try:
                yield self.process_filing(filing_id, html_content)
            except Exception as e:
                logger.warning(
                    "Failed to process %s %s: %s",
                    filing_id.ticker,
                    filing_id.accession_number,
                    str(e),
                )
                continue
