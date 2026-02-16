"""Search page — semantic search across ingested SEC filings."""

import streamlit as st

from sec_semantic_search.core import SearchResult
from sec_semantic_search.web._shared import get_registry, get_search_engine


# ---------------------------------------------------------------------------
# Sidebar — filters populated from the database
# ---------------------------------------------------------------------------


def _render_sidebar() -> tuple[str | None, str | None, int]:
    """Render the sidebar with ticker and form type filter controls.

    Returns:
        Tuple of (selected_ticker, selected_form_type, top_k).
        Ticker and form_type are ``None`` when "All" is selected.
    """
    st.sidebar.header("Filters")

    registry = get_registry()
    filings = registry.list_filings()

    tickers = sorted({f.ticker for f in filings})
    form_types = sorted({f.form_type for f in filings})

    # Ticker filter — "All" means no filter (None).
    ticker_options = ["All"] + tickers
    selected_ticker = st.sidebar.selectbox("Ticker", ticker_options)
    ticker = None if selected_ticker == "All" else selected_ticker

    # Form type filter.
    form_options = ["All"] + form_types
    selected_form = st.sidebar.selectbox("Form type", form_options)
    form_type = None if selected_form == "All" else selected_form

    # Number of results.
    top_k = st.sidebar.slider("Results", min_value=1, max_value=20, value=5)

    # Database summary.
    st.sidebar.divider()
    st.sidebar.caption(
        f"**{len(filings)}** filing(s) ingested "
        f"across **{len(tickers)}** ticker(s)"
    )

    return ticker, form_type, top_k


# ---------------------------------------------------------------------------
# Result rendering
# ---------------------------------------------------------------------------


def _similarity_colour(similarity: float) -> str:
    """Return a Streamlit colour name for the similarity score.

    Thresholds match the CLI (calibrated to embeddinggemma-300m):
    green >= 40 %, orange >= 25 %, red below.
    """
    if similarity >= 0.40:
        return "green"
    if similarity >= 0.25:
        return "orange"
    return "red"


def _render_result(rank: int, result: SearchResult) -> None:
    """Render a single search result as a styled container."""
    colour = _similarity_colour(result.similarity)
    pct = f"{result.similarity:.1%}"

    with st.container(border=True):
        header_left, header_right = st.columns([3, 1])

        with header_left:
            st.markdown(
                f"**#{rank}** &mdash; "
                f":{colour}[**{pct}**] similarity"
            )
        with header_right:
            source = f"**{result.ticker}** {result.form_type}"
            if result.filing_date:
                source += f" ({result.filing_date})"
            st.markdown(source)

        if result.path:
            st.caption(result.path)

        st.text(result.content[:500])


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------


def render() -> None:
    """Render the search page."""
    st.title("Search")
    st.caption("Search ingested SEC filings using natural language queries.")

    ticker, form_type, top_k = _render_sidebar()

    query = st.text_input(
        "Search query",
        placeholder="e.g. risk factors related to supply chain",
    )

    if not query:
        st.info("Enter a search query above to get started.")
        return

    engine = get_search_engine()

    with st.spinner("Searching..."):
        try:
            results = engine.search(
                query=query,
                top_k=top_k,
                ticker=ticker,
                form_type=form_type,
            )
        except Exception as e:
            st.error(f"Search failed: {e}")
            return

    if not results:
        st.warning(
            "No results found. Try a broader query, or check that "
            "filings have been ingested."
        )
        return

    st.subheader(f"{len(results)} result(s)")

    for i, result in enumerate(results, 1):
        _render_result(i, result)
