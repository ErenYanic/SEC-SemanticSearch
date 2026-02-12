"""Integration tests for the CLI commands via Typer's CliRunner.

CliRunner invokes commands programmatically without spawning subprocesses.
We mock heavy dependencies (fetcher, databases, embedder) to keep tests
fast while verifying exit codes, output messages, and command routing.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from typer.testing import CliRunner

from sec_semantic_search.cli.main import app
from sec_semantic_search.config.constants import EMBEDDING_DIMENSION
from sec_semantic_search.core.types import ContentType, IngestResult, Segment
from sec_semantic_search.pipeline.orchestrator import ProcessedFiling

runner = CliRunner()


# -----------------------------------------------------------------------
# Root app and version
# -----------------------------------------------------------------------


class TestRootApp:
    """The root app should show help and version."""

    def test_no_args_shows_help(self):
        """Typer's no_args_is_help=True exits with code 0 when run
        normally, but CliRunner returns exit code 0 or 2 depending on
        Click version. We just verify help text is shown."""
        result = runner.invoke(app, [])
        assert "Usage" in result.output or "sec-search" in result.output

    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "search" in result.output
        assert "ingest" in result.output
        assert "manage" in result.output

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "sec-search" in result.output


# -----------------------------------------------------------------------
# manage status
# -----------------------------------------------------------------------


class TestManageStatus:
    """manage status should display database statistics."""

    def test_empty_database(self, tmp_db_path, tmp_chroma_path):
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
            patch("sec_semantic_search.cli.manage.get_settings") as MockSettings,
        ):
            mock_registry = MagicMock()
            mock_registry.count.return_value = 0
            mock_registry.list_filings.return_value = []
            MockReg.return_value = mock_registry

            mock_chroma = MagicMock()
            mock_chroma.collection_count.return_value = 0
            MockChroma.return_value = mock_chroma

            mock_settings = MagicMock()
            mock_settings.database.max_filings = 20
            MockSettings.return_value = mock_settings

            result = runner.invoke(app, ["manage", "status"])

        assert result.exit_code == 0
        assert "0" in result.output


# -----------------------------------------------------------------------
# manage list
# -----------------------------------------------------------------------


class TestManageList:
    """manage list should show filings or a 'no filings' message."""

    def test_empty_list(self):
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = []
            MockReg.return_value = mock_registry

            result = runner.invoke(app, ["manage", "list"])

        assert result.exit_code == 0
        assert "No filings found" in result.output


# -----------------------------------------------------------------------
# manage remove
# -----------------------------------------------------------------------


class TestManageRemove:
    """manage remove should handle not-found and successful removal."""

    def test_not_found(self):
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.get_filing.return_value = None
            MockReg.return_value = mock_registry

            result = runner.invoke(app, ["manage", "remove", "NONEXISTENT"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# -----------------------------------------------------------------------
# search
# -----------------------------------------------------------------------


class TestSearchCommand:
    """The search command should display results or 'no results'."""

    def test_no_results(self):
        with patch("sec_semantic_search.cli.search.SearchEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.search.return_value = []
            MockEngine.return_value = mock_engine

            result = runner.invoke(app, ["search", "test query"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_search_error(self):
        from sec_semantic_search.core.exceptions import SearchError

        with patch("sec_semantic_search.cli.search.SearchEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.search.side_effect = SearchError("Search failed", details="No filings")
            MockEngine.return_value = mock_engine

            result = runner.invoke(app, ["search", "test query"])

        assert result.exit_code == 1
        assert "Search failed" in result.output


# -----------------------------------------------------------------------
# ingest add — validation
# -----------------------------------------------------------------------


class TestIngestAddValidation:
    """ingest add should validate form types before doing work."""

    def test_unsupported_form_type(self):
        result = runner.invoke(app, ["ingest", "add", "AAPL", "--form", "8-K"])
        assert result.exit_code == 1
        assert "Unsupported" in result.output


# -----------------------------------------------------------------------
# search _similarity_text helper
# -----------------------------------------------------------------------


class TestSimilarityText:
    """The _similarity_text helper colour-codes similarity percentages."""

    def test_high_similarity_green(self):
        from sec_semantic_search.cli.search import _similarity_text

        text = _similarity_text(0.45)
        assert "45.0%" in str(text)
        assert text.style == "bold green"

    def test_medium_similarity_yellow(self):
        from sec_semantic_search.cli.search import _similarity_text

        text = _similarity_text(0.30)
        assert "30.0%" in str(text)
        assert text.style == "yellow"

    def test_low_similarity_dim(self):
        from sec_semantic_search.cli.search import _similarity_text

        text = _similarity_text(0.10)
        assert "10.0%" in str(text)
        assert text.style == "dim"
