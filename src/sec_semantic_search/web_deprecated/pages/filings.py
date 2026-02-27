"""Filings page — view and manage ingested SEC filings."""

import streamlit as st

from sec_semantic_search.core import DatabaseError
from sec_semantic_search.database import FilingRecord
from sec_semantic_search.web_deprecated._shared import get_chroma, get_registry


# ---------------------------------------------------------------------------
# Delete confirmation dialog
# ---------------------------------------------------------------------------

# Streamlit's @st.dialog decorator creates a modal overlay — the web
# equivalent of the CLI's typer.confirm().  This adds deliberate friction
# before a destructive operation.


@st.dialog("Remove filing")
def _confirm_delete(filing: FilingRecord) -> None:
    """Show a confirmation dialog before deleting a filing."""
    st.markdown(
        f"**{filing.ticker}** {filing.form_type} ({filing.filing_date})"
    )
    st.caption(f"Accession: {filing.accession_number}")
    st.caption(f"Chunks: {filing.chunk_count}")

    st.warning("This will permanently remove the filing and its embeddings.")

    col_cancel, col_confirm = st.columns(2)

    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

    with col_confirm:
        if st.button(
            "Remove", type="primary", use_container_width=True
        ):
            _delete_filing(filing)


def _delete_filing(filing: FilingRecord) -> None:
    """Delete a filing from both stores and rerun the page."""
    registry = get_registry()
    chroma = get_chroma()

    # Deletion order: ChromaDB first, then SQLite — matching the CLI.
    try:
        chroma.delete_filing(filing.accession_number)
        registry.remove_filing(filing.accession_number)
    except DatabaseError as e:
        st.error(f"Removal failed: {e.message}")
        st.caption("Check that the data directory is writable.")
        return

    st.success(
        f"Removed **{filing.ticker}** {filing.form_type} "
        f"({filing.filing_date})"
    )
    st.rerun()


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------


def render() -> None:
    """Render the filings management page."""
    st.title("Filings")
    st.caption("View and manage ingested SEC filings.")

    registry = get_registry()

    # --- Filters -------------------------------------------------------------
    # Same pattern as the search sidebar but inline — this page is about
    # filing management, not search, so filters belong in the main area.

    col_ticker, col_form = st.columns([1, 1])

    filings_all = registry.list_filings()
    tickers = sorted({f.ticker for f in filings_all})
    form_types = sorted({f.form_type for f in filings_all})

    with col_ticker:
        ticker_options = ["All"] + tickers
        selected_ticker = st.selectbox("Ticker", ticker_options, key="filings_ticker")
        ticker = None if selected_ticker == "All" else selected_ticker

    with col_form:
        form_options = ["All"] + form_types
        selected_form = st.selectbox("Form type", form_options, key="filings_form")
        form_type = None if selected_form == "All" else selected_form

    # --- Filing list ---------------------------------------------------------

    filings = registry.list_filings(ticker=ticker, form_type=form_type)

    if not filings:
        st.info("No filings found. Ingest filings on the **Ingest** page.")
        return

    st.subheader(f"{len(filings)} filing(s)")

    for filing in filings:
        with st.container(border=True):
            col_info, col_action = st.columns([4, 1])

            with col_info:
                st.markdown(
                    f"**{filing.ticker}** {filing.form_type} "
                    f"&mdash; {filing.filing_date}"
                )
                st.caption(
                    f"Accession: {filing.accession_number}  |  "
                    f"Chunks: {filing.chunk_count}  |  "
                    f"Ingested: {filing.ingested_at}"
                )

            with col_action:
                # Each button needs a unique key — accession number is unique.
                if st.button(
                    "Remove",
                    key=f"del_{filing.accession_number}",
                    type="secondary",
                ):
                    _confirm_delete(filing)
