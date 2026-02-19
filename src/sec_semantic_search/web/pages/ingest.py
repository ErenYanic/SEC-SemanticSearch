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


def _ingest_one_form(
    ticker: str,
    form_type: str,
    *,
    registry,
    chroma,
    status,
    form_label: str = "",
) -> dict | None:
    """Run the full pipeline for one ticker and one form type.

    Returns a dict with filing_id and stats on success, or None on
    failure/skip (errors are displayed inline via st.error/st.warning).
    """
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
        return None

    # 2. Fetch the latest filing.
    st.write(f"Fetching latest {ticker} {form_type}{form_label}...")
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
        return None

    st.write(
        f"Fetched {ticker} {form_type} "
        f"({filing_id.date_str}, {filing_id.accession_number})"
    )

    # 3. Duplicate check.
    if registry.is_duplicate(filing_id.accession_number):
        st.warning(
            f"{ticker} {form_type} ({filing_id.date_str}) is "
            f"already in the database."
        )
        return None

    # 4. Process: parse → chunk → embed.
    st.write(f"Parsing{form_label}...")

    def _on_progress(step: str, _current: int, _total: int) -> None:
        if step != "Complete":
            st.write(f"{step}{form_label}...")

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
        return None

    # 5. Store: ChromaDB first, then SQLite.
    st.write(f"Storing{form_label}...")
    try:
        chroma.store_filing(result)
        registry.register_filing(
            result.filing_id, result.ingest_result.chunk_count
        )
    except DatabaseError as e:
        status.update(label="Storage failed", state="error")
        st.error(e.message)
        st.caption("Check disk space and that the data directory is writable.")
        return None

    return {
        "filing_id": filing_id,
        "form_type": form_type,
        "stats": result.ingest_result,
    }


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
            form_types = st.multiselect(
                "Form type(s)",
                SUPPORTED_FORMS,
                default=list(SUPPORTED_FORMS),
            )

        submitted = st.form_submit_button("Ingest filing(s)", type="primary")

    if not submitted:
        return

    # --- Validation ----------------------------------------------------------

    if not ticker:
        st.error("Please enter a ticker symbol.")
        return

    if not form_types:
        st.error("Please select at least one form type.")
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
    results = []

    with st.status("Ingesting filing(s)...", expanded=True) as status:
        for idx, form_type in enumerate(sorted(form_types)):
            form_label = (
                f" ({idx + 1}/{len(form_types)})"
                if len(form_types) > 1
                else ""
            )

            outcome = _ingest_one_form(
                ticker,
                form_type,
                registry=registry,
                chroma=chroma,
                status=status,
                form_label=form_label,
            )
            if outcome is not None:
                results.append(outcome)

        if results:
            status.update(label="Ingestion complete", state="complete")
        elif not results and len(form_types) > 0:
            # All forms were skipped or failed — status already set by helper.
            pass

    # --- Success summary -----------------------------------------------------

    if not results:
        return

    for r in results:
        filing_id = r["filing_id"]
        stats = r["stats"]
        st.success(
            f"Ingested **{ticker}** {r['form_type']} ({filing_id.date_str})"
        )

        col_seg, col_chunk, col_time = st.columns(3)
        col_seg.metric("Segments", stats.segment_count)
        col_chunk.metric("Chunks", stats.chunk_count)
        col_time.metric("Time", f"{stats.duration_seconds:.1f}s")
