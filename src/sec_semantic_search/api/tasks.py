"""
Background task manager for ingestion operations.

Provides ``TaskManager`` — an in-memory, single-process task runner that
executes ingestion pipelines in background threads.  Designed for a
single-user portfolio project running on a GTX 1650 (4 GB VRAM):

    - **One GPU task at a time** — a ``threading.Semaphore(1)`` gates
      execution; additional tasks queue in FIFO order.
    - **Cancel via ``threading.Event``** — checked between pipeline steps;
      partial data is rolled back on cancellation.
    - **Task cleanup** — completed/failed/cancelled tasks are pruned after
      one hour by a background timer.
    - **Progress callback** — the pipeline's ``progress_callback`` feeds
      directly into the task's ``TaskProgress`` snapshot.

No Redis, no Celery — task state lives in a plain ``dict``.
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sec_semantic_search.core import (
    DatabaseError,
    FetchError,
    FilingLimitExceededError,
    SECSemanticSearchError,
    get_logger,
)
from sec_semantic_search.database import ChromaDBClient, MetadataRegistry
from sec_semantic_search.pipeline import PipelineOrchestrator
from sec_semantic_search.pipeline.fetch import FilingFetcher, FilingInfo

logger = get_logger(__name__)

# Completed tasks are pruned after this many seconds.
_TASK_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Task state
# ---------------------------------------------------------------------------


class TaskState(str, Enum):
    """Lifecycle states for an ingestion task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskProgress:
    """Mutable progress snapshot updated by the worker thread."""

    current_ticker: str | None = None
    current_form_type: str | None = None
    step_label: str = ""
    step_index: int = 0
    step_total: int = 5
    filings_done: int = 0
    filings_total: int = 0
    filings_skipped: int = 0
    filings_failed: int = 0


@dataclass
class FilingResult:
    """Per-filing outcome stored after a successful ingest."""

    ticker: str
    form_type: str
    filing_date: str
    accession_number: str
    segment_count: int
    chunk_count: int
    duration_seconds: float


@dataclass
class TaskInfo:
    """
    Full state for a single ingestion task.

    Mutated by the worker thread; read by route handlers and WebSocket.
    Access to individual scalar/list fields is inherently thread-safe in
    CPython (GIL), but we avoid structural mutations to ``results`` from
    multiple threads.
    """

    task_id: str
    tickers: list[str]
    form_types: list[str]
    count_mode: str = "latest"
    count: int | None = None
    year: int | None = None
    start_date: str | None = None
    end_date: str | None = None

    state: TaskState = TaskState.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    results: list[FilingResult] = field(default_factory=list)
    error: str | None = None

    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Accession numbers stored so far in the *current* filing — used for
    # partial rollback on cancellation.
    _stored_accessions: list[str] = field(default_factory=list)

    # WebSocket message queue — worker thread pushes typed dicts,
    # WebSocket handler reads them for real-time progress streaming.
    _message_queue: queue.Queue = field(default_factory=queue.Queue)


# ---------------------------------------------------------------------------
# Task manager
# ---------------------------------------------------------------------------


class TaskManager:
    """
    In-memory manager for background ingestion tasks.

    Usage (from route handlers)::

        manager = TaskManager(registry, chroma, fetcher, orchestrator)
        task_id = manager.create_task(request)
        info = manager.get_task(task_id)
        manager.cancel_task(task_id)

    The manager is stored on ``app.state`` (singleton per process).
    """

    def __init__(
        self,
        registry: MetadataRegistry,
        chroma: ChromaDBClient,
        fetcher: FilingFetcher,
        orchestrator: PipelineOrchestrator,
    ) -> None:
        self._registry = registry
        self._chroma = chroma
        self._fetcher = fetcher
        self._orchestrator = orchestrator

        self._tasks: dict[str, TaskInfo] = {}
        self._gpu_semaphore = threading.Semaphore(1)
        self._lock = threading.Lock()  # protects _tasks dict mutations

        # Start the cleanup timer.
        self._start_cleanup_timer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(
        self,
        *,
        tickers: list[str],
        form_types: list[str],
        count_mode: str = "latest",
        count: int | None = None,
        year: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """
        Create a new ingestion task and start it in a background thread.

        Returns the task ID (UUID4 hex string).
        """
        task_id = uuid.uuid4().hex
        info = TaskInfo(
            task_id=task_id,
            tickers=tickers,
            form_types=form_types,
            count_mode=count_mode,
            count=count,
            year=year,
            start_date=start_date,
            end_date=end_date,
        )

        with self._lock:
            self._tasks[task_id] = info

        thread = threading.Thread(
            target=self._run_task,
            args=(info,),
            name=f"ingest-{task_id[:8]}",
            daemon=True,
        )
        thread.start()

        logger.info(
            "Created task %s: tickers=%s, forms=%s, mode=%s",
            task_id[:8],
            tickers,
            form_types,
            count_mode,
        )
        return task_id

    def get_task(self, task_id: str) -> TaskInfo | None:
        """Return task info or None if not found."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[TaskInfo]:
        """Return all tasks (active and recent)."""
        return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """
        Request cancellation of a running or pending task.

        Returns True if the cancel signal was sent, False if the task
        was not found or already finished.
        """
        info = self._tasks.get(task_id)
        if info is None:
            return False
        if info.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            return False
        info.cancel_event.set()
        logger.info("Cancel requested for task %s", task_id[:8])
        return True

    def has_active_task(self) -> bool:
        """Return True if any task is pending or running."""
        return any(
            t.state in (TaskState.PENDING, TaskState.RUNNING)
            for t in self._tasks.values()
        )

    # ------------------------------------------------------------------
    # WebSocket message helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _push(info: TaskInfo, message: dict) -> None:
        """Push a WebSocket message onto the task's queue."""
        info._message_queue.put(message)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _run_task(self, info: TaskInfo) -> None:
        """
        Execute the ingestion task.  Runs in a background thread.

        Acquires the GPU semaphore (blocking — FIFO queue), then
        iterates over tickers × form_types running the two-phase ingest
        pipeline.
        """
        # Wait for GPU slot (blocks if another task is running).
        logger.info("Task %s waiting for GPU slot...", info.task_id[:8])
        self._gpu_semaphore.acquire()

        try:
            # Check for cancellation while queued.
            if info.cancel_event.is_set():
                info.state = TaskState.CANCELLED
                info.completed_at = datetime.now(timezone.utc)
                self._push(info, {"type": "cancelled"})
                return

            info.state = TaskState.RUNNING
            info.started_at = datetime.now(timezone.utc)

            self._execute(info)

        except Exception as exc:
            info.state = TaskState.FAILED
            info.error = str(exc)
            info.completed_at = datetime.now(timezone.utc)
            self._push(info, {
                "type": "failed",
                "error": str(exc),
                "details": None,
            })
            logger.exception("Task %s failed unexpectedly", info.task_id[:8])
        finally:
            self._gpu_semaphore.release()

    def _execute(self, info: TaskInfo) -> None:
        """
        Core ingestion logic — mirrors the CLI two-phase ingest.

        Steps per filing:
            1. Fetch (cheap)
            2. Duplicate check
            3. Process (parse → chunk → embed — expensive GPU)
            4. Store (ChromaDB first, then SQLite)
        """
        # Build the flat work list of filings to ingest.
        work = self._build_work_list(info)

        info.progress.filings_total = len(work)

        for filing_id, html_content in work:
            # --- Cancellation check (between filings) --------------------
            if info.cancel_event.is_set():
                self._rollback(info)
                info.state = TaskState.CANCELLED
                info.completed_at = datetime.now(timezone.utc)
                self._push(info, {"type": "cancelled"})
                logger.info("Task %s cancelled", info.task_id[:8])
                return

            ticker = filing_id.ticker
            form_type = filing_id.form_type

            info.progress.current_ticker = ticker
            info.progress.current_form_type = form_type
            info.progress.step_label = "Checking duplicate"
            info.progress.step_index = 1

            # --- Duplicate check -----------------------------------------
            if self._registry.is_duplicate(filing_id.accession_number):
                info.progress.filings_skipped += 1
                info.progress.filings_done += 1
                self._push(info, {
                    "type": "filing_skipped",
                    "ticker": ticker,
                    "form_type": form_type,
                    "accession_number": filing_id.accession_number,
                    "reason": "duplicate",
                })
                logger.info(
                    "Task %s: skipped duplicate %s",
                    info.task_id[:8],
                    filing_id.accession_number,
                )
                continue

            # --- Filing limit check --------------------------------------
            try:
                self._registry.check_filing_limit()
            except FilingLimitExceededError as exc:
                info.state = TaskState.FAILED
                info.error = exc.message
                info.completed_at = datetime.now(timezone.utc)
                self._push(info, {
                    "type": "failed",
                    "error": exc.message,
                    "details": exc.details,
                })
                return

            # --- Process (parse → chunk → embed) -------------------------
            def _progress_cb(
                step: str,
                current: int,
                total: int,
                _info: TaskInfo = info,
                _ticker: str = ticker,
                _form: str = form_type,
            ) -> None:
                """Feed pipeline progress into task state."""
                _info.progress.current_ticker = _ticker
                _info.progress.current_form_type = _form
                _info.progress.step_label = step
                # Pipeline reports steps 1–4 (parse, chunk, embed, complete).
                # We add fetching as step 0 and storing as step 4, giving
                # 5 total: 0=fetch, 1=parse, 2=chunk, 3=embed, 4=store.
                _info.progress.step_index = current  # 1-based from pipeline
                _info.progress.step_total = 5

                TaskManager._push(_info, {
                    "type": "step",
                    "ticker": _ticker,
                    "form_type": _form,
                    "step": step,
                    "step_number": current,
                    "total_steps": 5,
                })

                # Check cancellation between pipeline steps.
                if _info.cancel_event.is_set():
                    raise _CancelledError

            info.progress.step_label = "Processing"
            info.progress.step_index = 1

            try:
                result = self._orchestrator.process_filing(
                    filing_id, html_content, progress_callback=_progress_cb,
                )
            except _CancelledError:
                self._rollback(info)
                info.state = TaskState.CANCELLED
                info.completed_at = datetime.now(timezone.utc)
                self._push(info, {"type": "cancelled"})
                logger.info("Task %s cancelled during processing", info.task_id[:8])
                return
            except SECSemanticSearchError as exc:
                info.progress.filings_failed += 1
                info.progress.filings_done += 1
                self._push(info, {
                    "type": "filing_failed",
                    "ticker": ticker,
                    "form_type": form_type,
                    "accession_number": filing_id.accession_number,
                    "error": exc.message,
                })
                logger.warning(
                    "Task %s: processing failed for %s — %s",
                    info.task_id[:8],
                    filing_id.accession_number,
                    exc.message,
                )
                continue

            # --- Store (ChromaDB first, then SQLite) ---------------------
            info.progress.step_label = "Storing"
            info.progress.step_index = 4

            if info.cancel_event.is_set():
                self._rollback(info)
                info.state = TaskState.CANCELLED
                info.completed_at = datetime.now(timezone.utc)
                self._push(info, {"type": "cancelled"})
                return

            try:
                self._chroma.store_filing(result)
                self._registry.register_filing(
                    result.filing_id, result.ingest_result.chunk_count,
                )
            except DatabaseError as exc:
                info.progress.filings_failed += 1
                info.progress.filings_done += 1
                self._push(info, {
                    "type": "filing_failed",
                    "ticker": ticker,
                    "form_type": form_type,
                    "accession_number": filing_id.accession_number,
                    "error": exc.message,
                })
                logger.warning(
                    "Task %s: storage failed for %s — %s",
                    info.task_id[:8],
                    filing_id.accession_number,
                    exc.message,
                )
                continue

            # Record success.
            info._stored_accessions.append(filing_id.accession_number)
            info.results.append(
                FilingResult(
                    ticker=filing_id.ticker,
                    form_type=filing_id.form_type,
                    filing_date=filing_id.date_str,
                    accession_number=filing_id.accession_number,
                    segment_count=result.ingest_result.segment_count,
                    chunk_count=result.ingest_result.chunk_count,
                    duration_seconds=result.ingest_result.duration_seconds,
                )
            )
            info.progress.filings_done += 1

            self._push(info, {
                "type": "filing_done",
                "ticker": filing_id.ticker,
                "form_type": filing_id.form_type,
                "filing_date": filing_id.date_str,
                "accession_number": filing_id.accession_number,
                "segments": result.ingest_result.segment_count,
                "chunks": result.ingest_result.chunk_count,
                "time": round(result.ingest_result.duration_seconds, 1),
            })

            logger.info(
                "Task %s: ingested %s %s (%s) — %d chunks in %.1fs",
                info.task_id[:8],
                filing_id.ticker,
                filing_id.form_type,
                filing_id.date_str,
                result.ingest_result.chunk_count,
                result.ingest_result.duration_seconds,
            )

        # All filings processed — mark complete.
        if info.state == TaskState.RUNNING:
            info.state = TaskState.COMPLETED
            info.completed_at = datetime.now(timezone.utc)
            info.progress.step_label = "Complete"
            self._push(info, {
                "type": "completed",
                "results": [
                    {
                        "ticker": r.ticker,
                        "form_type": r.form_type,
                        "filing_date": r.filing_date,
                        "accession_number": r.accession_number,
                        "segments": r.segment_count,
                        "chunks": r.chunk_count,
                        "time": round(r.duration_seconds, 1),
                    }
                    for r in info.results
                ],
                "summary": {
                    "ingested": len(info.results),
                    "skipped": info.progress.filings_skipped,
                    "failed": info.progress.filings_failed,
                },
            })
            logger.info(
                "Task %s completed: %d ingested, %d skipped, %d failed",
                info.task_id[:8],
                len(info.results),
                info.progress.filings_skipped,
                info.progress.filings_failed,
            )

    # ------------------------------------------------------------------
    # Work list builder
    # ------------------------------------------------------------------

    def _build_work_list(
        self,
        info: TaskInfo,
    ) -> list[tuple]:
        """
        Build a flat list of ``(FilingIdentifier, html_content)`` tuples.

        Mirrors the CLI's fetch-first approach: materialise all filings
        upfront so ``FetchError`` surfaces early, not mid-loop.
        """
        work: list[tuple] = []

        for ticker in info.tickers:
            if info.cancel_event.is_set():
                break

            info.progress.current_ticker = ticker
            info.progress.step_label = "Fetching"
            info.progress.step_index = 0

            if info.count_mode == "total" and info.count is not None:
                # Cross-form mode: list available across forms, pick
                # the newest `count`, then fetch each by accession.
                filings = self._list_across_forms(
                    ticker, tuple(info.form_types), info,
                )
                for fi in filings:
                    try:
                        fid, html = self._fetcher.fetch_by_accession(
                            fi.ticker, fi.form_type, fi.accession_number,
                        )
                        work.append((fid, html))
                    except FetchError as exc:
                        logger.warning(
                            "Task %s: fetch failed for %s — %s",
                            info.task_id[:8],
                            fi.accession_number,
                            exc.message,
                        )
            else:
                # Per-form mode.
                for form_type in info.form_types:
                    if info.cancel_event.is_set():
                        break

                    info.progress.current_form_type = form_type
                    effective_count = self._effective_count(info)

                    try:
                        fetched = list(self._fetcher.fetch(
                            ticker,
                            form_type,
                            count=effective_count,
                            year=info.year,
                            start_date=info.start_date,
                            end_date=info.end_date,
                        ))
                        work.extend(fetched)
                    except FetchError as exc:
                        logger.warning(
                            "Task %s: fetch failed for %s %s — %s",
                            info.task_id[:8],
                            ticker,
                            form_type,
                            exc.message,
                        )

        return work

    def _list_across_forms(
        self,
        ticker: str,
        form_types: tuple[str, ...],
        info: TaskInfo,
    ) -> list[FilingInfo]:
        """List and merge available filings across form types, newest first."""
        all_available: list[FilingInfo] = []
        for form_type in form_types:
            try:
                available = self._fetcher.list_available(
                    ticker, form_type,
                    count=info.count,
                    year=info.year,
                    start_date=info.start_date,
                    end_date=info.end_date,
                )
                all_available.extend(available)
            except FetchError:
                continue
        all_available.sort(key=lambda fi: fi.filing_date, reverse=True)
        return all_available[: info.count]

    @staticmethod
    def _effective_count(info: TaskInfo) -> int | None:
        """
        Determine the number of filings to fetch per form type.

        Mirrors the CLI's filter-aware default count logic.
        """
        if info.count_mode == "per_form" and info.count is not None:
            return info.count
        has_filters = (
            info.year is not None
            or info.start_date is not None
            or info.end_date is not None
        )
        if has_filters and info.count is None:
            return None  # all matching within filters
        if info.count is not None:
            return info.count
        return 1  # default: latest only

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _rollback(self, info: TaskInfo) -> None:
        """
        Roll back any filings stored during the current task.

        Called on cancellation to maintain dual-store consistency.
        Deletes from ChromaDB first, then SQLite (matching store order).
        """
        if not info._stored_accessions:
            return

        logger.info(
            "Task %s: rolling back %d filing(s)",
            info.task_id[:8],
            len(info._stored_accessions),
        )

        for accession in info._stored_accessions:
            try:
                self._chroma.delete_filing(accession)
                self._registry.remove_filing(accession)
            except DatabaseError as exc:
                logger.error(
                    "Task %s: rollback failed for %s — %s",
                    info.task_id[:8],
                    accession,
                    exc.message,
                )

        info._stored_accessions.clear()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _start_cleanup_timer(self) -> None:
        """Schedule periodic pruning of stale tasks."""
        timer = threading.Timer(60.0, self._cleanup_loop)
        timer.daemon = True
        timer.start()

    def _cleanup_loop(self) -> None:
        """Prune finished tasks older than TTL, then reschedule."""
        try:
            self._prune_stale_tasks()
        except Exception:
            logger.exception("Task cleanup error")
        finally:
            self._start_cleanup_timer()

    def _prune_stale_tasks(self) -> None:
        """Remove completed/failed/cancelled tasks older than the TTL."""
        now = time.time()
        terminal = (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)
        to_remove: list[str] = []

        for task_id, info in self._tasks.items():
            if info.state not in terminal:
                continue
            if info.completed_at is None:
                continue
            age = now - info.completed_at.timestamp()
            if age > _TASK_TTL_SECONDS:
                to_remove.append(task_id)

        if to_remove:
            with self._lock:
                for task_id in to_remove:
                    del self._tasks[task_id]
            logger.info("Pruned %d stale task(s)", len(to_remove))


# ---------------------------------------------------------------------------
# Internal sentinel exception for cancellation during pipeline
# ---------------------------------------------------------------------------


class _CancelledError(Exception):
    """Raised inside a progress callback to abort the pipeline."""