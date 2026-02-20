"""Ingest page — fetch and store SEC filings."""

from __future__ import annotations

from datetime import date

import streamlit as st

from sec_semantic_search.config import SUPPORTED_FORMS
from sec_semantic_search.core import (
    DatabaseError,
    FetchError,
    FilingLimitExceededError,
    SECSemanticSearchError,
)
from sec_semantic_search.pipeline import PipelineOrchestrator
from sec_semantic_search.pipeline.fetch import FilingFetcher, FilingInfo
from sec_semantic_search.web._shared import get_chroma, get_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _process_and_store(
    filing_id,
    html_content: str,
    form_type: str,
    *,
    fetcher: FilingFetcher,
    registry,
    chroma,
    status,
    label: str = "",
) -> dict | None:
    """Process a single pre-fetched filing and store it.

    Returns a result dict on success, or ``None`` on failure (errors are
    displayed inline).
    """
    # Process: parse → chunk → embed.
    def _on_progress(step: str, _current: int, _total: int) -> None:
        if step != "Complete":
            st.write(f"{step}{label}...")

    try:
        orchestrator = PipelineOrchestrator(fetcher=fetcher)
        result = orchestrator.process_filing(
            filing_id, html_content, progress_callback=_on_progress,
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

    # Store: ChromaDB first, then SQLite.
    st.write(f"Storing{label}...")
    try:
        chroma.store_filing(result)
        registry.register_filing(
            result.filing_id, result.ingest_result.chunk_count,
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


def _ingest_one_form(
    ticker: str,
    form_type: str,
    *,
    count: int = 1,
    year: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    registry,
    chroma,
    status,
    form_label: str = "",
) -> list[dict]:
    """Run the full pipeline for one ticker and one form type.

    Returns a list of dicts (one per successfully ingested filing), each
    containing ``filing_id``, ``form_type``, and ``stats``.  Errors and
    skips are displayed inline via ``st.error`` / ``st.warning``.
    """
    results: list[dict] = []

    # --- Filing limit check --------------------------------------------------
    try:
        registry.check_filing_limit()
    except FilingLimitExceededError as e:
        status.update(label="Filing limit reached", state="error")
        st.error(f"{e.message}")
        st.caption(
            "Remove filings on the **Filings** page, or raise "
            "the limit via `DB_MAX_FILINGS` in `.env`."
        )
        return results

    # --- Fetch ---------------------------------------------------------------
    has_filters = year is not None or start_date is not None or end_date is not None

    if count == 1 and not has_filters:
        st.write(f"Fetching latest {ticker} {form_type}{form_label}...")
    else:
        st.write(f"Fetching up to {count} {ticker} {form_type} filing(s){form_label}...")

    try:
        fetcher = FilingFetcher()
        if count == 1 and not has_filters:
            filings = [fetcher.fetch_latest(ticker, form_type)]
        elif count == 1:
            filings = [fetcher.fetch_one(
                ticker, form_type,
                year=year, start_date=start_date, end_date=end_date,
            )]
        else:
            filings = list(fetcher.fetch(
                ticker, form_type,
                count=count, year=year,
                start_date=start_date, end_date=end_date,
            ))
    except FetchError as e:
        status.update(label="Fetch failed", state="error")
        st.error(e.message)
        if e.details:
            st.caption(e.details)
        st.caption(
            "Check the ticker symbol is valid and you have an "
            "internet connection."
        )
        return results

    if not filings:
        st.warning(
            f"No {form_type} filings found for {ticker} with the given filters."
        )
        return results

    st.write(f"Found {len(filings)} filing(s).")

    # --- Process each filing -------------------------------------------------
    for filing_idx, (filing_id, html_content) in enumerate(filings):
        multi = len(filings) > 1
        filing_num = f" [{filing_idx + 1}/{len(filings)}]" if multi else ""

        st.write(
            f"Processing{filing_num}: {ticker} {form_type} "
            f"({filing_id.date_str}, {filing_id.accession_number})"
        )

        # Filing-limit re-check for subsequent filings.
        if filing_idx > 0:
            try:
                registry.check_filing_limit()
            except FilingLimitExceededError:
                st.warning(
                    f"Filing limit reached after {len(results)} ingestion(s) — stopping."
                )
                break

        # Duplicate check.
        if registry.is_duplicate(filing_id.accession_number):
            st.warning(
                f"{ticker} {form_type} ({filing_id.date_str}) is "
                f"already in the database."
            )
            continue

        outcome = _process_and_store(
            filing_id, html_content, form_type,
            fetcher=fetcher, registry=registry, chroma=chroma,
            status=status, label=f"{form_label}{filing_num}",
        )
        if outcome is not None:
            results.append(outcome)

    return results


def _ingest_across_forms(
    ticker: str,
    form_types: list[str],
    *,
    count: int,
    year: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    registry,
    chroma,
    status,
) -> list[dict]:
    """Ingest the *count* most recent filings across all *form_types*.

    Uses ``list_available()`` to preview filings from each form type,
    merges by date, selects the newest *count*, then fetches, processes,
    and stores each one.
    """
    results: list[dict] = []

    # --- Filing limit check --------------------------------------------------
    try:
        registry.check_filing_limit()
    except FilingLimitExceededError as e:
        status.update(label="Filing limit reached", state="error")
        st.error(f"{e.message}")
        st.caption(
            "Remove filings on the **Filings** page, or raise "
            "the limit via `DB_MAX_FILINGS` in `.env`."
        )
        return results

    # --- List available filings across form types ----------------------------
    st.write(
        f"Listing available {ticker} filings across "
        f"{', '.join(sorted(form_types))}..."
    )
    fetcher = FilingFetcher()
    all_available: list[FilingInfo] = []

    for form_type in sorted(form_types):
        try:
            available = fetcher.list_available(
                ticker, form_type, count=count,
                year=year, start_date=start_date, end_date=end_date,
            )
            all_available.extend(available)
        except FetchError:
            continue

    all_available.sort(key=lambda fi: fi.filing_date, reverse=True)
    selected = all_available[:count]

    if not selected:
        st.warning(f"No filings found for {ticker} with the given filters.")
        return results

    st.write(
        f"Selected {len(selected)} filing(s): "
        + ", ".join(f"{fi.form_type} ({fi.filing_date})" for fi in selected)
    )

    # --- Fetch, process, and store each selected filing ----------------------
    for filing_idx, fi in enumerate(selected):
        filing_num = f" [{filing_idx + 1}/{len(selected)}]"
        label = f"{fi.form_type}{filing_num}"

        # Filing-limit re-check.
        if filing_idx > 0:
            try:
                registry.check_filing_limit()
            except FilingLimitExceededError:
                st.warning(
                    f"Filing limit reached after {len(results)} ingestion(s) — stopping."
                )
                break

        # Duplicate check (before expensive fetch).
        if registry.is_duplicate(fi.accession_number):
            st.warning(
                f"{ticker} {fi.form_type} ({fi.filing_date}) is "
                f"already in the database."
            )
            continue

        # Fetch HTML content.
        st.write(f"Fetching{filing_num}: {ticker} {fi.form_type} ({fi.filing_date})...")
        try:
            filing_id, html_content = fetcher.fetch_by_accession(
                fi.ticker, fi.form_type, fi.accession_number,
            )
        except FetchError as e:
            st.error(f"Fetch failed{filing_num}: {e.message}")
            continue

        outcome = _process_and_store(
            filing_id, html_content, fi.form_type,
            fetcher=fetcher, registry=registry, chroma=chroma,
            status=status, label=filing_num,
        )
        if outcome is not None:
            results.append(outcome)

    return results


# ---------------------------------------------------------------------------
# Page render
# ---------------------------------------------------------------------------

def render() -> None:
    """Render the ingest page."""
    st.title("Ingest")
    st.caption("Fetch and store SEC filings for semantic search.")

    # --- Input form ----------------------------------------------------------
    # Using st.form() so the page only reruns on submit, not on every
    # keystroke.  This prevents accidental re-ingestion and keeps the UX
    # clean — the user fills in all fields, then clicks one button.

    current_year = date.today().year

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

        # Filing count controls.
        count_mode = st.radio(
            "How many filings?",
            ["Latest (1 per form)", "Total across forms", "Per form type"],
            horizontal=True,
        )

        filing_count: int | None = None
        if count_mode == "Total across forms":
            filing_count = st.number_input(
                "Total number of filings (newest first, across all form types)",
                min_value=1,
                max_value=20,
                value=3,
            )
        elif count_mode == "Per form type":
            filing_count = st.number_input(
                "Number of filings per form type",
                min_value=1,
                max_value=20,
                value=2,
            )

        # Optional filters.
        col_year, col_empty = st.columns(2)
        with col_year:
            year = st.number_input(
                "Filing year (optional)",
                min_value=1993,
                max_value=current_year,
                value=None,
                step=1,
                placeholder="Any",
            )

        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Start date (optional)", value=None)
        with col_end:
            end_date = st.date_input("End date (optional)", value=None)

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
    registry = get_registry()
    chroma = get_chroma()
    results: list[dict] = []

    with st.status("Ingesting filing(s)...", expanded=True) as status:
        if count_mode == "Total across forms":
            # Cross-form mode: newest N filings across all form types.
            results = _ingest_across_forms(
                ticker, sorted(form_types),
                count=filing_count,
                year=year,
                start_date=start_date,
                end_date=end_date,
                registry=registry,
                chroma=chroma,
                status=status,
            )
        else:
            # Per-form mode: latest or N per form type.
            effective_count = filing_count if filing_count is not None else 1

            for idx, form_type in enumerate(sorted(form_types)):
                form_label = (
                    f" ({idx + 1}/{len(form_types)})"
                    if len(form_types) > 1
                    else ""
                )

                outcome = _ingest_one_form(
                    ticker,
                    form_type,
                    count=effective_count,
                    year=year,
                    start_date=start_date,
                    end_date=end_date,
                    registry=registry,
                    chroma=chroma,
                    status=status,
                    form_label=form_label,
                )
                results.extend(outcome)

        if results:
            status.update(label="Ingestion complete", state="complete")

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