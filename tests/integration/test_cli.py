"""
Integration tests for the CLI commands via Typer's CliRunner.

CliRunner invokes commands programmatically without spawning subprocesses.
We mock heavy dependencies (fetcher, databases, embedder) to keep tests
fast while verifying exit codes, output messages, and command routing.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from typer.testing import CliRunner

from sec_semantic_search.cli.main import app
from sec_semantic_search.cli.manage import _delete_filings
from sec_semantic_search.config.constants import EMBEDDING_DIMENSION
from sec_semantic_search.core.types import ContentType, IngestResult, Segment
from sec_semantic_search.pipeline.orchestrator import ProcessedFiling
from tests.helpers import make_filing_record

runner = CliRunner()


# -----------------------------------------------------------------------
# Root app and version
# -----------------------------------------------------------------------


class TestRootApp:
    """The root app should show help and version."""

    def test_no_args_shows_help(self):
        """
        Typer's no_args_is_help=True exits with code 0 when run
        normally, but CliRunner returns exit code 0 or 2 depending on
        Click version. We just verify help text is shown.
        """
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
        assert "Database Status" in result.output
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
    """manage remove should handle not-found, successful, and cancelled removal."""

    def test_not_found(self):
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.get_filing.return_value = None
            MockReg.return_value = mock_registry

            result = runner.invoke(app, ["manage", "remove", "NONEXISTENT"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        assert "NONEXISTENT" in result.output

    def test_successful_removal_with_yes(self):
        """--yes bypasses confirmation and removes the filing."""
        record = make_filing_record(accession_number="ACC-001")
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
        ):
            mock_registry = MagicMock()
            mock_registry.get_filing.return_value = record
            MockReg.return_value = mock_registry

            mock_chroma = MagicMock()
            mock_chroma.delete_filing.return_value = 100
            MockChroma.return_value = mock_chroma

            result = runner.invoke(app, ["manage", "remove", "ACC-001", "--yes"])

        assert result.exit_code == 0
        assert "Removed" in result.output
        assert "100 chunks" in result.output

    def test_confirmation_rejected(self):
        """Answering 'n' to the confirmation prompt should cancel removal."""
        record = make_filing_record(accession_number="ACC-001")
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.get_filing.return_value = record
            MockReg.return_value = mock_registry

            result = runner.invoke(
                app, ["manage", "remove", "ACC-001"], input="n\n"
            )

        assert "Cancelled" in result.output


# -----------------------------------------------------------------------
# manage remove — bulk deletion
# -----------------------------------------------------------------------


class TestBulkRemove:
    """manage remove --ticker/--form should delete matching filings in bulk."""

    def test_bulk_remove_by_ticker(self):
        records = [
            make_filing_record(id=1, accession_number="ACC-001"),
            make_filing_record(id=2, accession_number="ACC-002"),
        ]
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
        ):
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = records
            MockReg.return_value = mock_registry

            mock_chroma = MagicMock()
            mock_chroma.delete_filing.return_value = 50
            MockChroma.return_value = mock_chroma

            result = runner.invoke(
                app, ["manage", "remove", "--ticker", "AAPL", "--yes"]
            )

        assert result.exit_code == 0
        assert "2 filing(s) removed" in result.output

    def test_bulk_remove_no_matches(self):
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = []
            MockReg.return_value = mock_registry

            result = runner.invoke(
                app, ["manage", "remove", "--ticker", "ZZZZ", "--yes"]
            )

        assert "No filings found" in result.output

    def test_mutual_exclusion_accession_and_ticker(self):
        """Providing both an accession number and --ticker should fail."""
        result = runner.invoke(
            app, ["manage", "remove", "ACC-001", "--ticker", "AAPL"]
        )
        assert result.exit_code == 1
        assert "Cannot combine" in result.output

    def test_no_args_no_filters(self):
        """Providing neither accession nor filters should fail."""
        result = runner.invoke(app, ["manage", "remove"])
        assert result.exit_code == 1
        assert "Provide an accession" in result.output.lower() or \
               "provide an accession" in result.output.lower()

    def test_bulk_remove_cancelled(self):
        """Answering 'n' to bulk remove confirmation should cancel."""
        records = [make_filing_record(accession_number="ACC-001")]
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
        ):
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = records
            MockReg.return_value = mock_registry
            MockChroma.return_value = MagicMock()

            result = runner.invoke(
                app, ["manage", "remove", "--ticker", "AAPL"], input="n\n"
            )

        assert "Cancelled" in result.output


# -----------------------------------------------------------------------
# manage clear
# -----------------------------------------------------------------------


class TestManageClear:
    """manage clear should delete all filings or report empty database."""

    def test_clear_with_yes(self):
        records = [
            make_filing_record(id=1, accession_number="ACC-001"),
            make_filing_record(id=2, accession_number="ACC-002"),
        ]
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
        ):
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = records
            MockReg.return_value = mock_registry

            mock_chroma = MagicMock()
            mock_chroma.delete_filing.return_value = 50
            MockChroma.return_value = mock_chroma

            result = runner.invoke(app, ["manage", "clear", "--yes"])

        assert result.exit_code == 0
        assert "Database cleared" in result.output

    def test_clear_empty_database(self):
        with patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg:
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = []
            MockReg.return_value = mock_registry

            result = runner.invoke(app, ["manage", "clear", "--yes"])

        assert result.exit_code == 0
        assert "already empty" in result.output.lower()

    def test_clear_cancelled(self):
        records = [make_filing_record(accession_number="ACC-001")]
        with (
            patch("sec_semantic_search.cli.manage.MetadataRegistry") as MockReg,
            patch("sec_semantic_search.cli.manage.ChromaDBClient") as MockChroma,
        ):
            mock_registry = MagicMock()
            mock_registry.list_filings.return_value = records
            MockReg.return_value = mock_registry
            MockChroma.return_value = MagicMock()

            result = runner.invoke(app, ["manage", "clear"], input="n\n")

        assert "Cancelled" in result.output


# -----------------------------------------------------------------------
# _delete_filings() helper
# -----------------------------------------------------------------------


class TestDeleteFilingsHelper:
    """_delete_filings() orchestrates deletion across both stores."""

    def test_deletes_multiple_returns_total_chunks(self):
        records = [
            make_filing_record(id=1, accession_number="ACC-001"),
            make_filing_record(id=2, accession_number="ACC-002"),
        ]
        mock_chroma = MagicMock()
        mock_chroma.delete_filing.return_value = 50
        mock_registry = MagicMock()

        total = _delete_filings(records, registry=mock_registry, chroma=mock_chroma)

        assert total == 100
        assert mock_chroma.delete_filing.call_count == 2
        assert mock_registry.remove_filing.call_count == 2

    def test_chromadb_called_before_sqlite(self):
        """Deletion order must be ChromaDB first, then SQLite."""
        record = make_filing_record(accession_number="ACC-001")
        call_order = []

        mock_chroma = MagicMock()
        mock_chroma.delete_filing.side_effect = lambda acc: (
            call_order.append(("chroma", acc)) or 50
        )
        mock_registry = MagicMock()
        mock_registry.remove_filing.side_effect = lambda acc: (
            call_order.append(("registry", acc))
        )

        _delete_filings([record], registry=mock_registry, chroma=mock_chroma)

        assert call_order == [
            ("chroma", "ACC-001"),
            ("registry", "ACC-001"),
        ]

    def test_empty_list_returns_zero(self):
        mock_chroma = MagicMock()
        mock_registry = MagicMock()

        total = _delete_filings([], registry=mock_registry, chroma=mock_chroma)

        assert total == 0
        mock_chroma.delete_filing.assert_not_called()
        mock_registry.remove_filing.assert_not_called()


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

    def test_multi_form_type_accepted(self):
        """Comma-separated valid forms should pass validation."""
        with patch("sec_semantic_search.cli.ingest.FilingFetcher") as MockFetcher:
            from sec_semantic_search.core.exceptions import FetchError

            mock_fetcher = MagicMock()
            mock_fetcher.fetch_latest.side_effect = FetchError("No network")
            MockFetcher.return_value = mock_fetcher

            result = runner.invoke(
                app, ["ingest", "add", "AAPL", "--form", "10-K,10-Q"]
            )

        # The form type validation should pass — any error is from fetching,
        # not from form type parsing.
        assert "Unsupported" not in result.output


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
