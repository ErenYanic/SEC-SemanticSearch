"""
Streamlit web interface for SEC-SemanticSearch.

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

from sec_semantic_search.web.pages.dashboard import render as dashboard_render  # noqa: E402
from sec_semantic_search.web.pages.filings import render as filings_render  # noqa: E402
from sec_semantic_search.web.pages.ingest import render as ingest_render  # noqa: E402
from sec_semantic_search.web.pages.search import render as search_render  # noqa: E402

pages = st.navigation(
    [
        st.Page(dashboard_render, title="Dashboard", icon=":material/dashboard:", url_path="dashboard"),
        st.Page(search_render, title="Search", icon=":material/search:", url_path="search"),
        st.Page(ingest_render, title="Ingest", icon=":material/download:", url_path="ingest"),
        st.Page(filings_render, title="Filings", icon=":material/folder:", url_path="filings"),
    ]
)
pages.run()
