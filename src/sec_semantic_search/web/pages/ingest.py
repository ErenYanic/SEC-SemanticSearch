"""Ingest page — fetch and store SEC filings."""

import streamlit as st

from sec_semantic_search.config import SUPPORTED_FORMS
from sec_semantic_search.core import (
    DatabaseError,
    FetchError,
    FilingLimitExceededError,
    SECSemanticSearchError,
)
from sec_semantic_search.pipeline import PipelineOrchestrator
from sec_semantic_search.pipeline.fetch import FilingFetcher
from sec_semantic_search.web._shared import get_chroma, get_registry


def render() -> None:
    """Render the ingest page."""
    st.title("Ingest")
    st.caption("Fetch and store SEC filings for semantic search.")

    # --- Input form ----------------------------------------------------------
    # Using st.form() so the page only reruns on submit, not on every
    # keystroke.  This prevents accidental re-ingestion and keeps the UX
    # clean — the user fills in both fields, then clicks one button.

    with st.form("ingest_form"):
        col_ticker, col_form = st.columns([2, 1])

        with col_ticker:
            ticker = st.text_input(
                "Ticker symbol",
                placeholder="e.g. AAPL",
            ).strip().upper()

        with col_form:
            form_type = st.selectbox("Form type", SUPPORTED_FORMS)

        submitted = st.form_submit_button("Ingest filing", type="primary")

    if not submitted:
        return

    # --- Validation ----------------------------------------------------------

    if not ticker:
        st.error("Please enter a ticker symbol.")
        return

    # --- Pipeline execution --------------------------------------------------
    # Mirrors the CLI's two-phase approach (cli/ingest.py):
    #   1. Check filing limit (cheap)
    #   2. Fetch the filing (network call — gets accession number)
    #   3. Check for duplicates (SQLite lookup)
    #   4. Process: parse → chunk → embed (expensive GPU work)
    #   5. Store: ChromaDB first, then SQLite

    registry = get_registry()
    chroma = get_chroma()

    with st.status("Ingesting filing...", expanded=True) as status:

        # 1. Filing limit check.
        try:
            registry.check_filing_limit()
        except FilingLimitExceededError as e:
            status.update(label="Filing limit reached", state="error")
            st.error(f"{e.message}")
            st.caption(
                "Remove filings on the **Filings** page, or raise "
                "the limit via `DB_MAX_FILINGS` in `.env`."
            )
            return

        # 2. Fetch the latest filing.
        st.write(f"Fetching latest {ticker} {form_type}...")
        try:
            fetcher = FilingFetcher()
            filing_id, html_content = fetcher.fetch_latest(ticker, form_type)
        except FetchError as e:
            status.update(label="Fetch failed", state="error")
            st.error(e.message)
            if e.details:
                st.caption(e.details)
            st.caption(
                "Check the ticker symbol is valid and you have an "
                "internet connection."
            )
            return

        st.write(
            f"Fetched {ticker} {form_type} "
            f"({filing_id.date_str}, {filing_id.accession_number})"
        )

        # 3. Duplicate check.
        if registry.is_duplicate(filing_id.accession_number):
            status.update(label="Already ingested", state="complete")
            st.warning(
                f"{ticker} {form_type} ({filing_id.date_str}) is "
                f"already in the database."
            )
            return

        # 4. Process: parse → chunk → embed.
        st.write("Parsing...")

        def _on_progress(step: str, _current: int, _total: int) -> None:
            if step != "Complete":
                st.write(f"{step}...")

        try:
            orchestrator = PipelineOrchestrator(fetcher=fetcher)
            result = orchestrator.process_filing(
                filing_id, html_content, progress_callback=_on_progress
            )
        except SECSemanticSearchError as e:
            status.update(label="Processing failed", state="error")
            st.error(e.message)
            if e.details:
                st.caption(e.details)
            st.caption(
                "If this is a memory error, try lowering "
                "`EMBEDDING_BATCH_SIZE` in `.env`."
            )
            return

        # 5. Store: ChromaDB first, then SQLite.
        st.write("Storing...")
        try:
            chroma.store_filing(result)
            registry.register_filing(
                result.filing_id, result.ingest_result.chunk_count
            )
        except DatabaseError as e:
            status.update(label="Storage failed", state="error")
            st.error(e.message)
            st.caption("Check disk space and that the data directory is writable.")
            return

        status.update(label="Ingestion complete", state="complete")

    # --- Success summary -----------------------------------------------------

    stats = result.ingest_result
    st.success(
        f"Ingested **{ticker}** {form_type} ({filing_id.date_str})"
    )

    col_seg, col_chunk, col_time = st.columns(3)
    col_seg.metric("Segments", stats.segment_count)
    col_chunk.metric("Chunks", stats.chunk_count)
    col_time.metric("Time", f"{stats.duration_seconds:.1f}s")
