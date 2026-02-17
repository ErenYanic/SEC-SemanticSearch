"""Dashboard page — statistics overview and form type breakdown."""

import pandas as pd
import streamlit as st

from sec_semantic_search.config import get_settings
from sec_semantic_search.web._shared import get_chroma, get_registry


def render() -> None:
    """Render the dashboard page with database statistics."""
    st.title("Dashboard")
    st.caption("Overview of ingested SEC filings and storage statistics.")

    registry = get_registry()
    chroma = get_chroma()
    settings = get_settings()

    filings = registry.list_filings()
    filing_count = len(filings)
    chunk_count = chroma.collection_count()
    max_filings = settings.database.max_filings

    # --- Key metrics ---------------------------------------------------------
    # st.metric() renders large, prominent numbers — the natural choice for a
    # dashboard header.  Three columns mirror the ingest success summary layout.

    col_filings, col_chunks, col_tickers = st.columns(3)

    unique_tickers = sorted({f.ticker for f in filings})

    col_filings.metric("Filings", f"{filing_count}/{max_filings}")
    col_chunks.metric("Chunks", f"{chunk_count:,}")
    col_tickers.metric("Tickers", len(unique_tickers))

    if not filings:
        st.info("No filings ingested yet. Head to the **Ingest** page to get started.")
        return

    # --- Form type breakdown chart -------------------------------------------
    # A bar chart is the natural fit for categorical data (form types) with
    # counts.  Streamlit's st.bar_chart() uses Altair under the hood and
    # requires zero extra configuration.

    st.subheader("Filings by form type")

    form_counts: dict[str, int] = {}
    for f in filings:
        form_counts[f.form_type] = form_counts.get(f.form_type, 0) + 1

    form_df = pd.DataFrame(
        {"Form type": list(form_counts.keys()), "Count": list(form_counts.values())}
    )
    st.bar_chart(form_df, x="Form type", y="Count", horizontal=True)

    # --- Per-ticker breakdown ------------------------------------------------
    # Gives users a quick view of their ingested data without navigating to
    # the Filings page — mirrors the CLI's ``manage status`` ticker list.

    st.subheader("Filings by ticker")

    ticker_rows: list[dict[str, str | int]] = []
    for ticker in unique_tickers:
        ticker_filings = [f for f in filings if f.ticker == ticker]
        total_chunks = sum(f.chunk_count for f in ticker_filings)
        forms = ", ".join(sorted({f.form_type for f in ticker_filings}))
        ticker_rows.append(
            {
                "Ticker": ticker,
                "Filings": len(ticker_filings),
                "Chunks": total_chunks,
                "Forms": forms,
            }
        )

    st.dataframe(
        pd.DataFrame(ticker_rows),
        use_container_width=True,
        hide_index=True,
    )
