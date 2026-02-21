"""
SQLite metadata registry for tracking ingested SEC filings.

This module provides a lightweight relational layer for operations that
ChromaDB does not handle well: duplicate detection, listing with filters,
aggregation statistics, and filing limit enforcement.

Usage:
    from sec_semantic_search.database import MetadataRegistry

    registry = MetadataRegistry()
    registry.register_filing(filing_id, chunk_count=59)
    filings = registry.list_filings(ticker="AAPL")
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sec_semantic_search.config import get_settings
from sec_semantic_search.core import (
    DatabaseError,
    FilingIdentifier,
    FilingLimitExceededError,
    get_logger,
)

logger = get_logger(__name__)


@dataclass
class FilingRecord:
    """
    A single row from the filings table.

    Provides typed access to filing metadata rather than raw tuples or dicts.
    Used by the CLI ``manage list`` and ``manage status`` commands.

    Attributes:
        id: Auto-increment primary key.
        ticker: Stock ticker symbol (e.g., "AAPL").
        form_type: SEC form type (e.g., "10-K").
        filing_date: Filing date as ISO string (YYYY-MM-DD).
        accession_number: SEC accession number (unique).
        chunk_count: Number of chunks stored in ChromaDB.
        ingested_at: ISO timestamp of when the filing was ingested.
    """

    id: int
    ticker: str
    form_type: str
    filing_date: str
    accession_number: str
    chunk_count: int
    ingested_at: str


class MetadataRegistry:
    """
    SQLite registry for tracking ingested SEC filings.

    This class manages a single ``filings`` table that records which filings
    have been ingested, their chunk counts, and ingestion timestamps. It
    provides duplicate detection, listing, statistics, and filing limit
    enforcement.

    The database file is created automatically on first use. The table
    schema is created via ``CREATE TABLE IF NOT EXISTS``, so repeated
    initialisation is safe.

    Example:
        >>> registry = MetadataRegistry()
        >>> registry.register_filing(filing_id, chunk_count=59)
        >>> print(registry.count())
        1
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialise the metadata registry.

        Args:
            db_path: Path to SQLite database file. If None, uses
                     ``settings.database.metadata_db_path``.
        """
        settings = get_settings()
        self._db_path = db_path or settings.database.metadata_db_path
        self._max_filings = settings.database.max_filings

        # Ensure parent directory exists
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create table on init (idempotent)
        self._create_table()

        logger.debug("MetadataRegistry initialised: %s", self._db_path)

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection with row factory enabled."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_table(self) -> None:
        """Create the filings table if it does not exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                form_type TEXT NOT NULL,
                filing_date TEXT NOT NULL,
                accession_number TEXT NOT NULL UNIQUE,
                chunk_count INTEGER NOT NULL,
                ingested_at TEXT NOT NULL,
                UNIQUE(ticker, form_type, filing_date)
            )
        """
        try:
            with self._connect() as conn:
                conn.execute(sql)
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to create metadata table",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Pre-ingestion checks
    # ------------------------------------------------------------------

    def check_filing_limit(self) -> None:
        """
        Raise FilingLimitExceededError if the filing limit is reached.

        This should be called before ingesting a new filing to prevent
        exceeding the configured maximum.

        Raises:
            FilingLimitExceededError: If current count >= max_filings.
            DatabaseError: If the query fails.
        """
        current = self.count()
        if current >= self._max_filings:
            raise FilingLimitExceededError(current, self._max_filings)

    def is_duplicate(self, accession_number: str) -> bool:
        """
        Check whether a filing has already been ingested.

        Args:
            accession_number: SEC accession number to check.

        Returns:
            True if the filing exists in the registry.

        Raises:
            DatabaseError: If the query fails.
        """
        sql = "SELECT 1 FROM filings WHERE accession_number = ? LIMIT 1"
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (accession_number,)).fetchone()
            return row is not None
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to check for duplicate filing",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def register_filing(
        self,
        filing_id: FilingIdentifier,
        chunk_count: int,
    ) -> None:
        """
        Register a newly ingested filing in the metadata registry.

        Args:
            filing_id: Identifier of the ingested filing.
            chunk_count: Number of chunks stored in ChromaDB.

        Raises:
            DatabaseError: If the insert fails (e.g., duplicate).
        """
        sql = """
            INSERT INTO filings (ticker, form_type, filing_date,
                                 accession_number, chunk_count, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        ingested_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    sql,
                    (
                        filing_id.ticker,
                        filing_id.form_type,
                        filing_id.date_str,
                        filing_id.accession_number,
                        chunk_count,
                        ingested_at,
                    ),
                )
            logger.info(
                "Registered filing: %s %s (%s) — %d chunks",
                filing_id.ticker,
                filing_id.form_type,
                filing_id.date_str,
                chunk_count,
            )
        except sqlite3.IntegrityError as e:
            raise DatabaseError(
                f"Filing already exists: {filing_id.accession_number}",
                details=str(e),
            ) from e
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to register filing",
                details=str(e),
            ) from e

    def remove_filing(self, accession_number: str) -> bool:
        """
        Remove a filing from the registry by accession number.

        Args:
            accession_number: SEC accession number of the filing to remove.

        Returns:
            True if a filing was removed, False if not found.

        Raises:
            DatabaseError: If the delete fails.
        """
        sql = "DELETE FROM filings WHERE accession_number = ?"
        try:
            with self._connect() as conn:
                cursor = conn.execute(sql, (accession_number,))
                removed = cursor.rowcount > 0
            if removed:
                logger.info(
                    "Removed filing from registry: %s", accession_number
                )
            else:
                logger.warning(
                    "Filing not found in registry: %s", accession_number
                )
            return removed
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to remove filing",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_filing(self, accession_number: str) -> Optional[FilingRecord]:
        """
        Retrieve a single filing record by accession number.

        Args:
            accession_number: SEC accession number.

        Returns:
            FilingRecord if found, None otherwise.

        Raises:
            DatabaseError: If the query fails.
        """
        sql = "SELECT * FROM filings WHERE accession_number = ?"
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (accession_number,)).fetchone()
            if row is None:
                return None
            return self._row_to_record(row)
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to retrieve filing",
                details=str(e),
            ) from e

    def list_filings(
        self,
        ticker: Optional[str] = None,
        form_type: Optional[str] = None,
    ) -> list[FilingRecord]:
        """
        List ingested filings with optional filters.

        Args:
            ticker: Filter by ticker symbol (case-insensitive).
            form_type: Filter by form type (case-insensitive).

        Returns:
            List of FilingRecord objects, ordered by filing_date descending.

        Raises:
            DatabaseError: If the query fails.
        """
        sql = "SELECT * FROM filings WHERE 1=1"
        params: list = []

        if ticker:
            sql += " AND ticker = ?"
            params.append(ticker.upper())
        if form_type:
            sql += " AND form_type = ?"
            params.append(form_type.upper())

        sql += " ORDER BY filing_date DESC"

        try:
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to list filings",
                details=str(e),
            ) from e

    def count(
        self,
        ticker: Optional[str] = None,
        form_type: Optional[str] = None,
    ) -> int:
        """
        Count ingested filings with optional filters.

        Args:
            ticker: Filter by ticker symbol.
            form_type: Filter by form type.

        Returns:
            Number of matching filings.

        Raises:
            DatabaseError: If the query fails.
        """
        sql = "SELECT COUNT(*) FROM filings WHERE 1=1"
        params: list = []

        if ticker:
            sql += " AND ticker = ?"
            params.append(ticker.upper())
        if form_type:
            sql += " AND form_type = ?"
            params.append(form_type.upper())

        try:
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
            return row[0]
        except sqlite3.Error as e:
            raise DatabaseError(
                "Failed to count filings",
                details=str(e),
            ) from e

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FilingRecord:
        """Convert a SQLite Row to a FilingRecord dataclass."""
        return FilingRecord(
            id=row["id"],
            ticker=row["ticker"],
            form_type=row["form_type"],
            filing_date=row["filing_date"],
            accession_number=row["accession_number"],
            chunk_count=row["chunk_count"],
            ingested_at=row["ingested_at"],
        )
