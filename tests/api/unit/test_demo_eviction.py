"""
Tests for FIFO eviction in demo mode (W5.7).

Covers:
    - ``MetadataRegistry.list_oldest_filings()`` — SQL ordering and LIMIT
    - ``TaskManager._maybe_evict()`` — eviction trigger logic
    - Demo mode per-filing limit check with eviction fallback
    - Non-demo mode preserves ``FilingLimitExceededError`` behaviour
    - WebSocket ``eviction`` message pushed on eviction
"""

from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.api.tasks import TaskManager, TaskState
from sec_semantic_search.core.exceptions import FilingLimitExceededError
from tests.helpers import make_filing_record, make_task_info


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


@pytest.fixture
def manager():
    """TaskManager with all dependencies mocked."""
    mock_registry = MagicMock()
    mock_registry.get_task_history.return_value = None
    with patch.object(TaskManager, "_start_cleanup_timer"):
        mgr = TaskManager(
            registry=mock_registry,
            chroma=MagicMock(),
            fetcher=MagicMock(),
            orchestrator=MagicMock(),
        )
    return mgr


def _make_oldest_filings(count: int, start_id: int = 1):
    """Create a list of filing records with sequential accession numbers."""
    return [
        make_filing_record(
            id=start_id + i,
            ticker="OLD",
            accession_number=f"0000000000-00-{i:06d}",
            chunk_count=10,
            ingested_at=f"2024-01-{i + 1:02d}T00:00:00",
        )
        for i in range(count)
    ]


# -----------------------------------------------------------------------
# list_oldest_filings (MetadataRegistry)
# -----------------------------------------------------------------------


class TestListOldestFilings:
    """list_oldest_filings returns filings ordered by ingested_at ASC."""

    def test_returns_limited_results(self, tmp_path):
        """Method respects the LIMIT parameter."""
        from datetime import date as date_cls

        from sec_semantic_search.core.types import FilingIdentifier
        from sec_semantic_search.database.metadata import MetadataRegistry

        registry = MetadataRegistry(db_path=str(tmp_path / "test.sqlite"))

        for i in range(5):
            registry.register_filing(
                FilingIdentifier(
                    ticker="AAPL",
                    form_type="10-K",
                    filing_date=date_cls(2024, 1, i + 1),
                    accession_number=f"0000000000-24-{i:06d}",
                ),
                chunk_count=10,
            )

        result = registry.list_oldest_filings(3)
        assert len(result) == 3

    def test_returns_oldest_first(self, tmp_path):
        """Filings are ordered by ingested_at ascending (oldest first)."""
        import time
        from datetime import date as date_cls

        from sec_semantic_search.core.types import FilingIdentifier
        from sec_semantic_search.database.metadata import MetadataRegistry

        registry = MetadataRegistry(db_path=str(tmp_path / "test.sqlite"))

        for i in range(3):
            registry.register_filing(
                FilingIdentifier(
                    ticker="AAPL",
                    form_type="10-K",
                    filing_date=date_cls(2024, i + 1, 1),
                    accession_number=f"0000000000-24-{i:06d}",
                ),
                chunk_count=10,
            )
            # Small delay to ensure different ingested_at timestamps.
            time.sleep(0.01)

        result = registry.list_oldest_filings(2)
        assert len(result) == 2
        # First result should be the earliest ingested.
        assert result[0].accession_number == "0000000000-24-000000"
        assert result[1].accession_number == "0000000000-24-000001"

    def test_returns_empty_for_empty_db(self, tmp_path):
        """Empty database returns empty list."""
        from sec_semantic_search.database.metadata import MetadataRegistry

        registry = MetadataRegistry(db_path=str(tmp_path / "test.sqlite"))
        assert registry.list_oldest_filings(10) == []

    def test_returns_all_when_limit_exceeds_count(self, tmp_path):
        """When limit > filing count, returns all filings."""
        from datetime import date as date_cls

        from sec_semantic_search.core.types import FilingIdentifier
        from sec_semantic_search.database.metadata import MetadataRegistry

        registry = MetadataRegistry(db_path=str(tmp_path / "test.sqlite"))

        for i in range(2):
            registry.register_filing(
                FilingIdentifier(
                    ticker="AAPL",
                    form_type="10-K",
                    filing_date=date_cls(2024, i + 1, 1),
                    accession_number=f"0000000000-24-{i:06d}",
                ),
                chunk_count=10,
            )

        result = registry.list_oldest_filings(100)
        assert len(result) == 2


# -----------------------------------------------------------------------
# _maybe_evict (TaskManager)
# -----------------------------------------------------------------------


class TestMaybeEvict:
    """_maybe_evict() triggers FIFO eviction when needed in demo mode."""

    def test_no_eviction_when_space_available(self, manager):
        """No eviction when there is enough room."""
        info = make_task_info(state=TaskState.RUNNING)

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 100
            mock_settings.return_value.api.demo_eviction_buffer = 10
            manager._registry.count.return_value = 50

            manager._maybe_evict(info, new_filings=10)

        # No deletion should occur.
        manager._registry.list_oldest_filings.assert_not_called()

    def test_eviction_triggered_when_over_limit(self, manager):
        """Eviction occurs when new filings would exceed the limit."""
        info = make_task_info(state=TaskState.RUNNING)
        oldest = _make_oldest_filings(15)
        manager._registry.list_oldest_filings.return_value = oldest
        manager._registry.count.return_value = 95

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 100
            mock_settings.return_value.api.demo_eviction_buffer = 10

            manager._maybe_evict(info, new_filings=10)

        # slots_needed = 10 - (100-95) = 5, eviction_count = 5 + 10 = 15
        manager._registry.list_oldest_filings.assert_called_once_with(15)

    def test_eviction_count_includes_buffer(self, manager):
        """Eviction count = slots_needed + buffer."""
        info = make_task_info(state=TaskState.RUNNING)
        oldest = _make_oldest_filings(503)
        manager._registry.list_oldest_filings.return_value = oldest
        manager._registry.count.return_value = 500

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 500
            mock_settings.return_value.api.demo_eviction_buffer = 500

            manager._maybe_evict(info, new_filings=3)

        # slots_needed = 3, eviction_count = 3 + 500 = 503, capped to 500
        manager._registry.list_oldest_filings.assert_called_once_with(500)

    def test_eviction_capped_to_current_count(self, manager):
        """Cannot evict more filings than currently stored."""
        info = make_task_info(state=TaskState.RUNNING)
        oldest = _make_oldest_filings(5)
        manager._registry.list_oldest_filings.return_value = oldest
        manager._registry.count.return_value = 5

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 5
            mock_settings.return_value.api.demo_eviction_buffer = 100

            manager._maybe_evict(info, new_filings=3)

        # eviction_count = 3 + 100 = 103, capped to current_count = 5
        manager._registry.list_oldest_filings.assert_called_once_with(5)

    def test_eviction_pushes_ws_message(self, manager):
        """Eviction pushes a WebSocket message with eviction details."""
        info = make_task_info(state=TaskState.RUNNING)
        oldest = _make_oldest_filings(3)
        manager._registry.list_oldest_filings.return_value = oldest
        manager._registry.count.return_value = 10

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 10
            mock_settings.return_value.api.demo_eviction_buffer = 0

            manager._maybe_evict(info, new_filings=5)

        # Check that eviction message was pushed.
        msg = info._message_queue.get_nowait()
        assert msg["type"] == "eviction"
        assert msg["filings_evicted"] == 3
        assert msg["chunks_evicted"] == 30  # 3 filings × 10 chunks each
        assert msg["tickers_affected"] == ["OLD"]

    def test_eviction_calls_delete_filings_batch(self, manager):
        """Eviction uses delete_filings_batch for dual-store deletion."""
        info = make_task_info(state=TaskState.RUNNING)
        oldest = _make_oldest_filings(2)
        manager._registry.list_oldest_filings.return_value = oldest
        manager._registry.count.return_value = 10

        with (
            patch("sec_semantic_search.api.tasks.get_settings") as mock_settings,
            patch("sec_semantic_search.api.tasks.delete_filings_batch") as mock_delete,
        ):
            mock_settings.return_value.database.max_filings = 10
            mock_settings.return_value.api.demo_eviction_buffer = 0
            mock_delete.return_value = 20  # chunks deleted

            manager._maybe_evict(info, new_filings=5)

        mock_delete.assert_called_once_with(
            oldest,
            chroma=manager._chroma,
            registry=manager._registry,
        )

    def test_no_eviction_when_empty_oldest_list(self, manager):
        """No crash when list_oldest_filings returns empty (edge case)."""
        info = make_task_info(state=TaskState.RUNNING)
        manager._registry.list_oldest_filings.return_value = []
        manager._registry.count.return_value = 10

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 10
            mock_settings.return_value.api.demo_eviction_buffer = 0

            # Should not raise.
            manager._maybe_evict(info, new_filings=5)

        assert info._message_queue.empty()

    def test_exact_boundary_no_eviction(self, manager):
        """When new_filings == available slots, no eviction needed."""
        info = make_task_info(state=TaskState.RUNNING)

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.database.max_filings = 100
            mock_settings.return_value.api.demo_eviction_buffer = 10
            manager._registry.count.return_value = 95

            manager._maybe_evict(info, new_filings=5)  # exactly 5 available

        manager._registry.list_oldest_filings.assert_not_called()


# -----------------------------------------------------------------------
# Per-filing limit check with demo mode fallback
# -----------------------------------------------------------------------


class TestDemoModeFilingLimitFallback:
    """In demo mode, per-filing limit check triggers eviction instead of failing."""

    def test_non_demo_mode_fails_on_limit(self, manager):
        """Without demo mode, FilingLimitExceededError fails the task."""
        info = make_task_info(state=TaskState.RUNNING)
        info.progress.filings_total = 1

        # Set up: work list with 1 non-duplicate filing
        mock_filing_info = MagicMock()
        mock_filing_info.accession_number = "0000000000-24-000001"
        mock_filing_info.to_identifier.return_value = MagicMock(
            ticker="AAPL", form_type="10-K",
            accession_number="0000000000-24-000001",
        )

        manager._build_work_list = MagicMock(return_value=[mock_filing_info])
        manager._registry.get_existing_accessions.return_value = set()
        # Cached count check: count >= max_filings triggers limit error.
        manager._registry.count.return_value = 500

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.api.demo_mode = False
            mock_settings.return_value.database.max_filings = 500
            manager._execute(info)

        assert info.state == TaskState.FAILED
        assert "Filing limit exceeded" in info.error

    def test_demo_mode_evicts_on_limit(self, manager):
        """In demo mode, per-filing limit check triggers eviction."""
        info = make_task_info(state=TaskState.RUNNING)
        info.progress.filings_total = 1

        mock_filing_info = MagicMock()
        mock_filing_info.accession_number = "0000000000-24-000001"
        mock_id = MagicMock(
            ticker="AAPL", form_type="10-K",
            accession_number="0000000000-24-000001",
            date_str="2024-01-01",
        )
        mock_filing_info.to_identifier.return_value = mock_id

        manager._build_work_list = MagicMock(return_value=[mock_filing_info])
        manager._registry.get_existing_accessions.return_value = set()

        # First call: raises limit error, second call (after eviction): passes
        manager._registry.check_filing_limit.side_effect = [
            FilingLimitExceededError(current_count=500, max_filings=500),
            None,  # After eviction, limit check passes
        ]

        manager._maybe_evict = MagicMock()

        # Mock the fetch to avoid actual EDGAR calls
        manager._fetcher.fetch_filing_content.return_value = (mock_id, "<html></html>")

        # Mock the orchestrator to return a processed filing
        mock_result = MagicMock()
        mock_result.filing_id = mock_id
        mock_result.ingest_result.segment_count = 10
        mock_result.ingest_result.chunk_count = 10
        mock_result.ingest_result.duration_seconds = 1.0
        manager._orchestrator.process_filing.return_value = mock_result

        # Mock storage to succeed
        manager._registry.register_filing_if_new.return_value = True

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.api.demo_mode = True
            mock_settings.return_value.database.max_filings = 500
            mock_settings.return_value.api.demo_eviction_buffer = 10
            # Initial count at limit; after eviction re-read returns below limit.
            manager._registry.count.side_effect = [500, 499]
            manager._registry.list_oldest_filings.return_value = _make_oldest_filings(5)

            manager._execute(info)

        # Task should not have failed — eviction should have been triggered.
        assert info.state != TaskState.FAILED
        # _maybe_evict should have been called (pre-loop + per-filing fallback).
        assert manager._maybe_evict.call_count >= 1


# -----------------------------------------------------------------------
# Pre-loop eviction in _execute
# -----------------------------------------------------------------------


class TestPreLoopEviction:
    """_execute() triggers pre-loop eviction in demo mode."""

    def test_pre_loop_eviction_called_with_non_duplicate_count(self, manager):
        """Pre-loop eviction calculates new_count from non-duplicate filings."""
        info = make_task_info(state=TaskState.RUNNING)

        # 3 filings total, 1 is a duplicate
        filings = [MagicMock(accession_number=f"ACC-{i}") for i in range(3)]
        for f in filings:
            f.to_identifier.return_value = MagicMock(
                ticker="AAPL", form_type="10-K",
                accession_number=f.accession_number,
            )

        manager._build_work_list = MagicMock(return_value=filings)
        manager._registry.get_existing_accessions.return_value = {"ACC-1"}
        manager._maybe_evict = MagicMock()

        # Cached count below limit so per-filing check passes.
        manager._registry.count.return_value = 50

        # Make fetch/process fail to stop the loop early
        manager._fetcher.fetch_filing_content.side_effect = Exception("stop")

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.api.demo_mode = True
            mock_settings.return_value.database.max_filings = 100
            mock_settings.return_value.api.demo_eviction_buffer = 10

            try:
                manager._execute(info)
            except Exception:
                pass

        # Pre-loop eviction should have been called with 2 (3 total - 1 duplicate)
        manager._maybe_evict.assert_called_once_with(info, 2)

    def test_no_pre_loop_eviction_when_not_demo(self, manager):
        """Pre-loop eviction is skipped when not in demo mode."""
        info = make_task_info(state=TaskState.RUNNING)

        filings = [MagicMock(accession_number="ACC-0")]
        filings[0].to_identifier.return_value = MagicMock(
            ticker="AAPL", form_type="10-K",
            accession_number="ACC-0",
        )

        manager._build_work_list = MagicMock(return_value=filings)
        manager._registry.get_existing_accessions.return_value = set()
        manager._maybe_evict = MagicMock()
        # Cached count below limit so per-filing check passes.
        manager._registry.count.return_value = 50
        manager._fetcher.fetch_filing_content.side_effect = Exception("stop")

        with patch("sec_semantic_search.api.tasks.get_settings") as mock_settings:
            mock_settings.return_value.api.demo_mode = False
            mock_settings.return_value.database.max_filings = 100

            try:
                manager._execute(info)
            except Exception:
                pass

        manager._maybe_evict.assert_not_called()
