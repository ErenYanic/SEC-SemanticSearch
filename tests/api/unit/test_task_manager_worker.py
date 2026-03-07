"""
Unit tests for TaskManager worker internals.

Covers the previously untested static/internal methods:
    - _effective_count() — 4 branches
    - _rollback() — success and error tolerance
    - _push() — WebSocket message queuing
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.api.tasks import TaskInfo, TaskManager, TaskState
from sec_semantic_search.core.exceptions import DatabaseError
from tests.helpers import make_task_info


# -----------------------------------------------------------------------
# _effective_count()
# -----------------------------------------------------------------------


class TestEffectiveCount:
    """_effective_count() determines how many filings to fetch per form."""

    def test_per_form_with_count(self):
        """per_form mode with explicit count should return that count."""
        info = make_task_info(count_mode="per_form", count=3)
        assert TaskManager._effective_count(info) == 3

    def test_per_form_without_count(self):
        """per_form mode without count falls through to default (1)."""
        info = make_task_info(count_mode="per_form", count=None)
        assert TaskManager._effective_count(info) == 1

    def test_latest_with_year_filter_no_count(self):
        """With date filters active and no explicit count, return None (all matching)."""
        info = make_task_info(count_mode="latest", count=None)
        info.year = 2023
        assert TaskManager._effective_count(info) is None

    def test_latest_with_start_date_filter(self):
        info = make_task_info(count_mode="latest", count=None)
        info.start_date = "2023-01-01"
        assert TaskManager._effective_count(info) is None

    def test_latest_with_end_date_filter(self):
        info = make_task_info(count_mode="latest", count=None)
        info.end_date = "2023-12-31"
        assert TaskManager._effective_count(info) is None

    def test_latest_with_explicit_count(self):
        """Explicit count should be used even in 'latest' mode."""
        info = make_task_info(count_mode="latest", count=5)
        assert TaskManager._effective_count(info) == 5

    def test_default_returns_one(self):
        """No filters, no count, 'latest' mode → default to 1."""
        info = make_task_info(count_mode="latest", count=None)
        assert TaskManager._effective_count(info) == 1

    def test_total_mode_with_count(self):
        """'total' mode with count — _effective_count is only called for per-form,
        but should still return the count if it falls through."""
        info = make_task_info(count_mode="total", count=5)
        # In total mode, _effective_count is called but count_mode != "per_form",
        # so it falls through. With count=5 and no filters, returns 5.
        assert TaskManager._effective_count(info) == 5


# -----------------------------------------------------------------------
# _rollback()
# -----------------------------------------------------------------------


@pytest.fixture
def manager():
    """TaskManager with all dependencies mocked."""
    with patch.object(TaskManager, "_start_cleanup_timer"):
        mgr = TaskManager(
            registry=MagicMock(),
            chroma=MagicMock(),
            fetcher=MagicMock(),
            orchestrator=MagicMock(),
        )
    return mgr


class TestRollback:
    """_rollback() cleans up partially stored filings on cancel."""

    def test_rollback_deletes_stored_accessions(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        info._stored_accessions = ["ACC-001", "ACC-002"]

        manager._rollback(info)

        assert manager._chroma.delete_filing.call_count == 2
        assert manager._registry.remove_filing.call_count == 2
        manager._chroma.delete_filing.assert_any_call("ACC-001")
        manager._chroma.delete_filing.assert_any_call("ACC-002")
        manager._registry.remove_filing.assert_any_call("ACC-001")
        manager._registry.remove_filing.assert_any_call("ACC-002")

    def test_rollback_clears_accessions_list(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        info._stored_accessions = ["ACC-001"]

        manager._rollback(info)

        assert info._stored_accessions == []

    def test_rollback_empty_list_is_noop(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        info._stored_accessions = []

        manager._rollback(info)

        manager._chroma.delete_filing.assert_not_called()
        manager._registry.remove_filing.assert_not_called()

    def test_rollback_tolerates_database_error(self, manager):
        """If one rollback fails, it should still attempt the rest."""
        info = make_task_info(state=TaskState.RUNNING)
        info._stored_accessions = ["ACC-001", "ACC-002"]

        manager._chroma.delete_filing.side_effect = [
            DatabaseError("fail"),
            50,
        ]

        # Should not raise — errors are logged, not propagated.
        manager._rollback(info)
        assert manager._chroma.delete_filing.call_count == 2

    def test_rollback_chromadb_first_then_sqlite(self, manager):
        """Rollback must follow the same order as store: ChromaDB then SQLite."""
        info = make_task_info(state=TaskState.RUNNING)
        info._stored_accessions = ["ACC-001"]

        call_order = []
        manager._chroma.delete_filing.side_effect = lambda acc: (
            call_order.append(("chroma", acc)) or 10
        )
        manager._registry.remove_filing.side_effect = lambda acc: (
            call_order.append(("registry", acc))
        )

        manager._rollback(info)

        assert call_order == [("chroma", "ACC-001"), ("registry", "ACC-001")]


# -----------------------------------------------------------------------
# _push()
# -----------------------------------------------------------------------


class TestPush:
    """_push() puts messages on the task's queue for WebSocket streaming."""

    def test_message_placed_on_queue(self):
        info = make_task_info()
        message = {"type": "step", "step": "Parsing"}

        TaskManager._push(info, message)

        assert not info._message_queue.empty()
        assert info._message_queue.get_nowait() == message

    def test_multiple_messages_fifo(self):
        info = make_task_info()
        TaskManager._push(info, {"type": "step", "step": "Parsing"})
        TaskManager._push(info, {"type": "step", "step": "Embedding"})
        TaskManager._push(info, {"type": "completed", "results": []})

        msgs = []
        while not info._message_queue.empty():
            msgs.append(info._message_queue.get_nowait())

        assert [m["type"] for m in msgs] == ["step", "step", "completed"]