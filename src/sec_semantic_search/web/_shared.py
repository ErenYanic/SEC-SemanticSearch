"""Shared cached resources for the Streamlit web interface.

All page modules import from here rather than creating their own
instances.  ``@st.cache_resource`` ensures each object is created once
and reused across Streamlit reruns and sessions.
"""

import streamlit as st

from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.search import SearchEngine


@st.cache_resource
def get_search_engine() -> SearchEngine:
    """Create a SearchEngine singleton.

    The embedding model (loaded lazily on first query) stays in GPU
    memory across reruns.
    """
    return SearchEngine()


@st.cache_resource
def get_registry() -> MetadataRegistry:
    """Create a MetadataRegistry singleton for filing queries."""
    return MetadataRegistry()


@st.cache_resource
def get_chroma() -> ChromaDBClient:
    """Create a ChromaDBClient singleton for vector store operations."""
    return ChromaDBClient()
