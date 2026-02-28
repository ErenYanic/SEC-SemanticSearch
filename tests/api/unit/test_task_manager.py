"""
Tests for the TaskManager background task runner.

TaskManager is tested with fully mocked dependencies (registry, chroma,
fetcher, orchestrator). The ``_run_task`` method is patched to prevent
actual background threads from spawning — we test the manager's own
bookkeeping logic, not the ingestion pipeline.
"""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from sec_semantic_search.api.tasks import TaskManager, TaskState, _TASK_TTL_SECONDS
from tests.helpers import make_task_info


@pytest.fixture
def manager():
    """TaskManager with all dependencies mocked and _run_task patched out."""
    with patch.object(TaskManager, "_start_cleanup_timer"):
        mgr = TaskManager(
            registry=MagicMock(),
            chroma=MagicMock(),
            fetcher=MagicMock(),
            orchestrator=MagicMock(),
        )
    return mgr


# -----------------------------------------------------------------------
# create_task
# -----------------------------------------------------------------------


class TestCreateTask:
    """Task creation stores TaskInfo and starts a thread."""

    def test_returns_hex_string(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        assert isinstance(task_id, str)
        assert len(task_id) == 32  # UUID4 hex

    def test_task_stored(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        info = manager.get_task(task_id)
        assert info is not None
        assert info.tickers == ["AAPL"]
        assert info.form_types == ["10-K"]

    def test_task_state_is_pending(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        assert manager.get_task(task_id).state == TaskState.PENDING

    def test_parameters_stored(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(
                tickers=["MSFT"],
                form_types=["10-Q"],
                count_mode="total",
                count=3,
                year=2023,
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
        info = manager.get_task(task_id)
        assert info.count_mode == "total"
        assert info.count == 3
        assert info.year == 2023
        assert info.start_date == "2023-01-01"
        assert info.end_date == "2023-12-31"


# -----------------------------------------------------------------------
# get_task
# -----------------------------------------------------------------------


class TestGetTask:
    """Task retrieval."""

    def test_existing_task(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        assert manager.get_task(task_id) is not None

    def test_nonexistent_task(self, manager):
        assert manager.get_task("nonexistent") is None


# -----------------------------------------------------------------------
# list_tasks
# -----------------------------------------------------------------------


class TestListTasks:
    """Task listing."""

    def test_empty(self, manager):
        assert manager.list_tasks() == []

    def test_multiple_tasks(self, manager):
        with patch.object(manager, "_run_task"):
            manager.create_task(tickers=["AAPL"], form_types=["10-K"])
            manager.create_task(tickers=["MSFT"], form_types=["10-Q"])
        assert len(manager.list_tasks()) == 2


# -----------------------------------------------------------------------
# cancel_task
# -----------------------------------------------------------------------


class TestCancelTask:
    """Task cancellation."""

    def test_pending_task(self, manager):
        with patch.object(manager, "_run_task"):
            task_id = manager.create_task(tickers=["AAPL"], form_types=["10-K"])
        assert manager.cancel_task(task_id) is True
        assert manager.get_task(task_id).cancel_event.is_set()

    def test_running_task(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        manager._tasks[info.task_id] = info
        assert manager.cancel_task(info.task_id) is True
        assert info.cancel_event.is_set()

    def test_completed_task_returns_false(self, manager):
        info = make_task_info(state=TaskState.COMPLETED)
        manager._tasks[info.task_id] = info
        assert manager.cancel_task(info.task_id) is False

    def test_failed_task_returns_false(self, manager):
        info = make_task_info(state=TaskState.FAILED)
        manager._tasks[info.task_id] = info
        assert manager.cancel_task(info.task_id) is False

    def test_cancelled_task_returns_false(self, manager):
        info = make_task_info(state=TaskState.CANCELLED)
        manager._tasks[info.task_id] = info
        assert manager.cancel_task(info.task_id) is False

    def test_nonexistent_task_returns_false(self, manager):
        assert manager.cancel_task("nonexistent") is False


# -----------------------------------------------------------------------
# has_active_task
# -----------------------------------------------------------------------


class TestHasActiveTask:
    """Active task detection."""

    def test_no_tasks(self, manager):
        assert manager.has_active_task() is False

    def test_pending_task(self, manager):
        info = make_task_info(state=TaskState.PENDING)
        manager._tasks[info.task_id] = info
        assert manager.has_active_task() is True

    def test_running_task(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        manager._tasks[info.task_id] = info
        assert manager.has_active_task() is True

    def test_completed_only(self, manager):
        info = make_task_info(state=TaskState.COMPLETED)
        manager._tasks[info.task_id] = info
        assert manager.has_active_task() is False

    def test_mix_with_one_active(self, manager):
        done = make_task_info(task_id="done1", state=TaskState.COMPLETED)
        active = make_task_info(task_id="active1", state=TaskState.RUNNING)
        manager._tasks[done.task_id] = done
        manager._tasks[active.task_id] = active
        assert manager.has_active_task() is True


# -----------------------------------------------------------------------
# Task cleanup
# -----------------------------------------------------------------------


class TestTaskCleanup:
    """Completed tasks are pruned after the TTL."""

    def test_old_completed_task_pruned(self, manager):
        info = make_task_info(state=TaskState.COMPLETED)
        info.completed_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        manager._tasks[info.task_id] = info
        manager._prune_stale_tasks()
        assert manager.get_task(info.task_id) is None

    def test_recent_completed_task_kept(self, manager):
        info = make_task_info(state=TaskState.COMPLETED)
        info.completed_at = datetime.now(timezone.utc)
        manager._tasks[info.task_id] = info
        manager._prune_stale_tasks()
        assert manager.get_task(info.task_id) is not None

    def test_running_task_never_pruned(self, manager):
        info = make_task_info(state=TaskState.RUNNING)
        manager._tasks[info.task_id] = info
        manager._prune_stale_tasks()
        assert manager.get_task(info.task_id) is not None

    def test_failed_task_pruned_after_ttl(self, manager):
        info = make_task_info(state=TaskState.FAILED)
        info.completed_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        manager._tasks[info.task_id] = info
        manager._prune_stale_tasks()
        assert manager.get_task(info.task_id) is None