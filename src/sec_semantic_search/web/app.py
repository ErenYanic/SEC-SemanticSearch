"""Streamlit web interface for SEC-SemanticSearch.

Multi-page application with search, ingest, and filing management pages.

Launch with:
    streamlit run src/sec_semantic_search/web/app.py

Or via the console script:
    sec-search-web
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SEC Semantic Search",
    page_icon=":mag:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Navigation — define pages and run the selected one
# ---------------------------------------------------------------------------

from sec_semantic_search.web.pages.filings import render as filings_render  # noqa: E402
from sec_semantic_search.web.pages.ingest import render as ingest_render  # noqa: E402
from sec_semantic_search.web.pages.search import render as search_render  # noqa: E402

pages = st.navigation(
    [
        st.Page(search_render, title="Search", icon=":material/search:"),
        st.Page(ingest_render, title="Ingest", icon=":material/download:"),
        st.Page(filings_render, title="Filings", icon=":material/folder:"),
    ]
)
pages.run()
