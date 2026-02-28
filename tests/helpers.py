"""
Shared test helper utilities for SEC-SemanticSearch tests.

Plain functions (not pytest fixtures) that can be imported directly
by test modules. Kept separate from conftest.py because conftest.py
is for fixtures only — plain helpers must be in a regular module to
be importable via standard Python imports.
"""

from sec_semantic_search.api.tasks import TaskInfo, TaskProgress, TaskState
from sec_semantic_search.database.metadata import FilingRecord


def make_filing_record(
    *,
    id: int = 1,
    ticker: str = "AAPL",
    form_type: str = "10-K",
    filing_date: str = "2024-11-01",
    accession_number: str = "0000320193-24-000001",
    chunk_count: int = 100,
    ingested_at: str = "2024-11-15T10:00:00",
) -> FilingRecord:
    """
    Factory for creating FilingRecord instances with sensible defaults.

    Not a fixture — accepts parameters so tests can create records with
    different values.
    """
    return FilingRecord(
        id=id,
        ticker=ticker,
        form_type=form_type,
        filing_date=filing_date,
        accession_number=accession_number,
        chunk_count=chunk_count,
        ingested_at=ingested_at,
    )


def make_task_info(
    *,
    task_id: str = "abc123def456",
    tickers: list[str] | None = None,
    form_types: list[str] | None = None,
    state: TaskState = TaskState.PENDING,
    count_mode: str = "latest",
    count: int | None = None,
    error: str | None = None,
) -> TaskInfo:
    """
    Factory for creating TaskInfo instances with sensible defaults.

    The cancel_event and message_queue are auto-created by the dataclass.
    """
    info = TaskInfo(
        task_id=task_id,
        tickers=tickers or ["AAPL"],
        form_types=form_types or ["10-K", "10-Q"],
        count_mode=count_mode,
        count=count,
    )
    info.state = state
    info.error = error
    return info
