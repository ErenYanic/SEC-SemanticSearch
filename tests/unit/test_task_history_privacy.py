"""
Tests for W5.3 Task History Privacy.

Covers:
    - Ticker stripping: tickers stored as null when TASK_HISTORY_PERSIST_TICKERS=false
    - Error message scrubbing: ticker symbols and accession numbers removed
    - Configurable retention: prune_task_history respects TASK_HISTORY_RETENTION_DAYS
"""

import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from sec_semantic_search.database.metadata import (
    MetadataRegistry,
    _scrub_error_message,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _reset_settings():
    """Reload settings after the test to avoid cross-test contamination."""
    yield
    from sec_semantic_search.config import reload_settings
    reload_settings()


@pytest.fixture
def registry(tmp_path, monkeypatch, _reset_settings):
    """Create a fresh MetadataRegistry with isolated paths."""
    monkeypatch.setenv("DB_METADATA_DB_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("DB_CHROMA_PATH", str(tmp_path / "chroma"))

    from sec_semantic_search.config import reload_settings
    reload_settings()

    # Explicit empty key ensures unencrypted mode regardless of
    # DB_ENCRYPTION_KEY in .env — tests that read the database file
    # directly via sqlite3 need plain (non-SQLCipher) databases.
    reg = MetadataRegistry(str(tmp_path / "test.sqlite"), encryption_key="")
    yield reg
    reg.close()


def _save_sample_task(
    registry,
    task_id="task-1",
    tickers=None,
    error=None,
    completed_at="2024-11-15T10:01:00+00:00",
):
    """Helper to save a sample task with sensible defaults."""
    registry.save_task_history(
        task_id,
        status="completed",
        tickers=tickers or ["AAPL", "MSFT"],
        form_types=["10-K"],
        results=[],
        error=error,
        started_at="2024-11-15T10:00:00+00:00",
        completed_at=completed_at,
        filings_done=1,
        filings_skipped=0,
        filings_failed=0,
    )


def _mock_settings(**overrides):
    """Return a patched get_settings with database setting overrides.

    Patches only the ``get_settings`` used inside ``metadata.py`` so the
    returned settings object reflects *overrides* without touching env
    vars or the real singleton (which has the frozen-default issue with
    nested BaseSettings in pydantic-settings v2).
    """
    from sec_semantic_search.config import get_settings

    real = get_settings()

    class FakeDB:
        """Thin proxy that overrides specific attributes."""

        def __getattr__(self, name):
            if name in overrides:
                return overrides[name]
            return getattr(real.database, name)

    class FakeSettings:
        def __getattr__(self, name):
            if name == "database":
                return FakeDB()
            return getattr(real, name)

    return patch(
        "sec_semantic_search.database.metadata.get_settings",
        return_value=FakeSettings(),
    )


# ---------------------------------------------------------------------------
# _scrub_error_message unit tests
# ---------------------------------------------------------------------------


class TestScrubErrorMessage:
    """Tests for the _scrub_error_message helper function."""

    def test_none_input(self):
        """None input returns None."""
        assert _scrub_error_message(None, ["AAPL"]) is None

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert _scrub_error_message("", ["AAPL"]) == ""

    def test_no_matches(self):
        """Message without tickers or accessions is unchanged."""
        msg = "Connection timed out"
        assert _scrub_error_message(msg, ["AAPL"]) == "Connection timed out"

    def test_ticker_replaced(self):
        """Known ticker symbols are replaced with [TICKER]."""
        msg = "Failed to fetch AAPL 10-K filing"
        result = _scrub_error_message(msg, ["AAPL"])
        assert "AAPL" not in result
        assert "[TICKER]" in result
        assert "10-K filing" in result

    def test_multiple_tickers(self):
        """Multiple different tickers are all replaced."""
        msg = "Error processing AAPL and MSFT filings"
        result = _scrub_error_message(msg, ["AAPL", "MSFT"])
        assert "AAPL" not in result
        assert "MSFT" not in result
        assert result.count("[TICKER]") == 2

    def test_ticker_case_insensitive(self):
        """Ticker matching is case-insensitive."""
        msg = "Failed for aapl filing"
        result = _scrub_error_message(msg, ["AAPL"])
        assert "aapl" not in result
        assert "[TICKER]" in result

    def test_ticker_word_boundary(self):
        """Ticker replacement respects word boundaries."""
        # "APPLE" should not match "AAPL" ticker
        msg = "APPLE is not AAPL"
        result = _scrub_error_message(msg, ["AAPL"])
        assert "APPLE" in result  # not replaced
        assert "[TICKER] " not in result.split("is")[0]  # APPLE untouched

    def test_accession_with_dashes(self):
        """Accession numbers with dashes are replaced."""
        msg = "Filing 0000320193-24-000001 not found"
        result = _scrub_error_message(msg, [])
        assert "0000320193-24-000001" not in result
        assert "[ACCESSION]" in result

    def test_accession_without_dashes(self):
        """Accession numbers without dashes are also replaced."""
        msg = "Filing 000032019324000001 not found"
        result = _scrub_error_message(msg, [])
        assert "000032019324000001" not in result
        assert "[ACCESSION]" in result

    def test_multiple_accessions(self):
        """Multiple accession numbers are all replaced."""
        msg = "Failed: 0000320193-24-000001 and 0000320193-24-000002"
        result = _scrub_error_message(msg, [])
        assert result.count("[ACCESSION]") == 2

    def test_combined_ticker_and_accession(self):
        """Both tickers and accession numbers are scrubbed simultaneously."""
        msg = "Failed to fetch AAPL filing 0000320193-24-000001"
        result = _scrub_error_message(msg, ["AAPL"])
        assert "AAPL" not in result
        assert "0000320193-24-000001" not in result
        assert "[TICKER]" in result
        assert "[ACCESSION]" in result

    def test_empty_tickers_list(self):
        """Empty tickers list only scrubs accession numbers."""
        msg = "Failed for AAPL 0000320193-24-000001"
        result = _scrub_error_message(msg, [])
        assert "AAPL" in result  # not scrubbed — not in tickers list
        assert "[ACCESSION]" in result

    def test_ticker_with_special_regex_chars(self):
        """Tickers that look like regex chars are escaped properly."""
        # Hypothetical ticker with dot (e.g. BRK.B)
        msg = "Failed for BRK.B filing"
        result = _scrub_error_message(msg, ["BRK.B"])
        assert "BRK.B" not in result
        assert "[TICKER]" in result


# ---------------------------------------------------------------------------
# Ticker stripping in save_task_history
# ---------------------------------------------------------------------------


class TestTickerStripping:
    """Tests for TASK_HISTORY_PERSIST_TICKERS behaviour."""

    def test_tickers_stripped_by_default(self, registry, tmp_path):
        """With default settings (persist=false), tickers are stored as null."""
        _save_sample_task(registry)

        # Verify at the raw SQL level — tickers column should be NULL.
        conn = sqlite3.connect(str(tmp_path / "test.sqlite"))
        row = conn.execute(
            "SELECT tickers FROM task_history WHERE task_id = ?", ("task-1",)
        ).fetchone()
        conn.close()

        assert row[0] is None

    def test_get_task_history_returns_empty_list_when_stripped(self, registry):
        """get_task_history returns [] for tickers when column is null."""
        _save_sample_task(registry)

        result = registry.get_task_history("task-1")
        assert result is not None
        assert result["tickers"] == []

    def test_tickers_persisted_when_enabled(self, registry, tmp_path):
        """When TASK_HISTORY_PERSIST_TICKERS=true, tickers are stored."""
        with _mock_settings(task_history_persist_tickers=True):
            _save_sample_task(registry, tickers=["AAPL", "MSFT"])

        # Raw SQL check — should be a JSON array.
        conn = sqlite3.connect(str(tmp_path / "test.sqlite"))
        row = conn.execute(
            "SELECT tickers FROM task_history WHERE task_id = ?",
            ("task-1",),
        ).fetchone()
        conn.close()
        assert json.loads(row[0]) == ["AAPL", "MSFT"]

        # API-level check.
        result = registry.get_task_history("task-1")
        assert result["tickers"] == ["AAPL", "MSFT"]

    def test_form_types_always_persisted(self, registry, tmp_path):
        """form_types are always stored regardless of the ticker setting."""
        _save_sample_task(registry)

        conn = sqlite3.connect(str(tmp_path / "test.sqlite"))
        row = conn.execute(
            "SELECT form_types FROM task_history WHERE task_id = ?",
            ("task-1",),
        ).fetchone()
        conn.close()
        assert json.loads(row[0]) == ["10-K"]


# ---------------------------------------------------------------------------
# Error scrubbing in save_task_history
# ---------------------------------------------------------------------------


class TestErrorScrubbing:
    """Tests for error message scrubbing during persistence."""

    def test_error_scrubbed_on_save(self, registry):
        """Ticker symbols and accessions are scrubbed from error messages."""
        _save_sample_task(
            registry,
            tickers=["AAPL"],
            error="Failed to fetch AAPL filing 0000320193-24-000001",
        )

        result = registry.get_task_history("task-1")
        assert result is not None
        assert "AAPL" not in result["error"]
        assert "0000320193-24-000001" not in result["error"]
        assert "[TICKER]" in result["error"]
        assert "[ACCESSION]" in result["error"]

    def test_null_error_stays_null(self, registry):
        """No error (None) is stored as-is without crashing."""
        _save_sample_task(registry, error=None)

        result = registry.get_task_history("task-1")
        assert result["error"] is None

    def test_error_scrubbed_even_when_tickers_persisted(self, registry):
        """Error scrubbing applies regardless of the ticker-persist setting."""
        with _mock_settings(task_history_persist_tickers=True):
            _save_sample_task(
                registry,
                tickers=["AAPL"],
                error="AAPL fetch failed at 0000320193-24-000001",
            )

        result = registry.get_task_history("task-1")
        # Tickers are persisted, but error is still scrubbed.
        assert result["tickers"] == ["AAPL"]
        assert "AAPL" not in result["error"]
        assert "[TICKER]" in result["error"]

    def test_error_without_identifiers_unchanged(self, registry):
        """Error messages without tickers/accessions pass through."""
        _save_sample_task(
            registry,
            error="Connection timed out after 30 seconds",
        )

        result = registry.get_task_history("task-1")
        assert result["error"] == "Connection timed out after 30 seconds"


# ---------------------------------------------------------------------------
# Configurable retention (prune_task_history)
# ---------------------------------------------------------------------------


class TestConfigurableRetention:
    """Tests for TASK_HISTORY_RETENTION_DAYS in prune_task_history."""

    def test_zero_retention_skips_pruning(self, registry):
        """When retention=0 (default), pruning is skipped entirely."""
        _save_sample_task(
            registry,
            completed_at="2020-01-01T00:00:00+00:00",
        )
        assert registry.get_task_history("task-1") is not None

        # Default setting = 0 → skip pruning.
        with _mock_settings(task_history_retention_days=0):
            removed = registry.prune_task_history()
        assert removed == 0
        assert registry.get_task_history("task-1") is not None

    def test_retention_prunes_old_entries(self, registry):
        """Entries older than retention days are pruned."""
        _save_sample_task(
            registry,
            completed_at="2020-01-01T00:00:00+00:00",
        )

        # Prune with explicit 1-day retention.
        removed = registry.prune_task_history(max_age_days=1)
        assert removed == 1
        assert registry.get_task_history("task-1") is None

    def test_retention_keeps_recent_entries(self, registry):
        """Entries newer than retention days are kept."""
        recent = datetime.now(timezone.utc).isoformat()
        _save_sample_task(registry, completed_at=recent)

        removed = registry.prune_task_history(max_age_days=30)
        assert removed == 0
        assert registry.get_task_history("task-1") is not None

    def test_retention_reads_from_settings(self, registry):
        """prune_task_history reads TASK_HISTORY_RETENTION_DAYS when no arg."""
        _save_sample_task(
            registry,
            completed_at="2020-01-01T00:00:00+00:00",
        )

        with _mock_settings(task_history_retention_days=1):
            removed = registry.prune_task_history()  # reads setting = 1
        assert removed == 1

    def test_mixed_old_and_new_entries(self, registry):
        """Only old entries are pruned; recent ones remain."""
        _save_sample_task(
            registry,
            task_id="old-task",
            completed_at="2020-01-01T00:00:00+00:00",
        )
        _save_sample_task(
            registry,
            task_id="new-task",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        removed = registry.prune_task_history(max_age_days=1)
        assert removed == 1
        assert registry.get_task_history("old-task") is None
        assert registry.get_task_history("new-task") is not None

    def test_negative_retention_skips_pruning(self, registry):
        """Negative retention days also skip pruning (defensive)."""
        _save_sample_task(
            registry,
            completed_at="2020-01-01T00:00:00+00:00",
        )
        removed = registry.prune_task_history(max_age_days=-1)
        assert removed == 0


# ---------------------------------------------------------------------------
# Task_history schema allows NULL tickers
# ---------------------------------------------------------------------------


class TestSchemaAllowsNullTickers:
    """Verify the task_history table schema permits NULL tickers."""

    def test_null_tickers_column(self, registry, tmp_path):
        """Direct SQL INSERT with NULL tickers succeeds."""
        conn = sqlite3.connect(str(tmp_path / "test.sqlite"))
        conn.execute(
            """
            INSERT INTO task_history
                (task_id, status, tickers, form_types, results,
                 filings_done, filings_skipped, filings_failed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("null-test", "completed", None, '["10-K"]', "[]", 0, 0, 0),
        )
        conn.commit()

        row = conn.execute(
            "SELECT tickers FROM task_history WHERE task_id = ?",
            ("null-test",),
        ).fetchone()
        conn.close()
        assert row[0] is None
