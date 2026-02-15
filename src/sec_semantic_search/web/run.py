"""Launch helper for the Streamlit web interface.

This module provides the ``main()`` entry point used by the
``sec-search-web`` console script defined in ``pyproject.toml``.

Streamlit apps cannot be invoked as plain Python callables — they
require ``streamlit run <file>``.  This wrapper resolves the path to
``app.py`` and delegates to Streamlit's CLI runner.
"""

import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit app via ``streamlit run``."""
    app_path = str(Path(__file__).parent / "app.py")
    sys.argv = ["streamlit", "run", app_path, "--server.headless=true"]

    from streamlit.web.cli import main as st_main

    st_main()
