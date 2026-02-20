"""
SEC filing fetcher using edgartools.

This module wraps the edgartools library to fetch SEC filings (10-K, 10-Q)
from the EDGAR database. It provides flexible selection methods including:
    - Single latest filing
    - Specific filing by index position
    - Multiple recent filings
    - Filter by year or year range
    - Filter by date range

Usage:
    from sec_semantic_search.pipeline import FilingFetcher

    fetcher = FilingFetcher()

    # Single latest filing
    filing_id, html = fetcher.fetch_latest("AAPL", "10-K")

    # Multiple filings (last 5 years)
    for filing_id, html in fetcher.fetch("AAPL", "10-K", count=5):
        process(filing_id, html)

    # Specific filing by index (0=most recent, 1=second most recent)
    filing_id, html = fetcher.fetch_one("AAPL", "10-K", index=2)

    # Filter by year range
    for filing_id, html in fetcher.fetch("AAPL", "10-Q", year=range(2020, 2025)):
        process(filing_id, html)

    # Filter by date range
    for filing_id, html in fetcher.fetch("AAPL", "10-K", start_date="2020-01-01"):
        process(filing_id, html)
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator

from edgar import Company, set_identity

from sec_semantic_search.config import SUPPORTED_FORMS, get_settings
from sec_semantic_search.core import FetchError, FilingIdentifier, get_logger

logger = get_logger(__name__)


@dataclass
class FilingInfo:
    """
    Summary information about an available filing (without content).

    This lightweight class is used by list_available() to preview
    filings before downloading their full HTML content.

    Attributes:
        ticker: Stock ticker symbol
        form_type: SEC form type (10-K, 10-Q)
        filing_date: Date filed with SEC
        accession_number: SEC-assigned unique identifier
        company_name: Full company name
    """

    ticker: str
    form_type: str
    filing_date: date
    accession_number: str
    company_name: str

    def to_identifier(self) -> FilingIdentifier:
        """Convert to FilingIdentifier for pipeline use."""
        return FilingIdentifier(
            ticker=self.ticker,
            form_type=self.form_type,
            filing_date=self.filing_date,
            accession_number=self.accession_number,
        )


class FilingFetcher:
    """
    Fetches SEC filings from EDGAR using edgartools.

    This class provides flexible methods for fetching SEC filings with
    various selection criteria. It handles identity configuration
    automatically using credentials from settings.

    Selection Methods:
        - fetch_latest(): Single most recent filing
        - fetch_one(): Single filing by index position
        - fetch(): Multiple filings with optional filters
        - list_available(): Preview filings without downloading

    Filter Options:
        - count: Maximum number of filings to fetch
        - index: Specific position (0=most recent)
        - year: Single year, list of years, or range
        - start_date/end_date: Date range filtering

    Attributes:
        settings: Application settings instance
        max_filings: Maximum filings limit from settings

    Example:
        >>> fetcher = FilingFetcher()
        >>> # Get last 5 years of 10-K filings
        >>> for filing_id, html in fetcher.fetch("AAPL", "10-K", count=5):
        ...     print(f"Processing {filing_id.date_str}")
    """

    def __init__(self) -> None:
        """Initialise the fetcher and configure EDGAR identity."""
        self.settings = get_settings()
        self.max_filings = self.settings.database.max_filings
        self._configure_identity()

    def _configure_identity(self) -> None:
        """
        Configure SEC EDGAR identity from settings.

        SEC EDGAR requires identification for API access. This sets
        the identity using credentials from environment variables.

        Raises:
            FetchError: If identity credentials are missing.
        """
        try:
            name = self.settings.edgar.identity_name
            email = self.settings.edgar.identity_email
            set_identity(f"{name} {email}")
            logger.debug("EDGAR identity configured: %s", email)
        except Exception as e:
            raise FetchError(
                "Failed to configure EDGAR identity",
                details=str(e),
            ) from e

    def _validate_form_type(self, form_type: str) -> str:
        """
        Validate and normalise form type.

        Args:
            form_type: SEC form type (e.g., "10-K", "10-Q")

        Returns:
            Normalised form type in uppercase.

        Raises:
            FetchError: If form type is not supported.
        """
        normalised = form_type.upper()
        if normalised not in SUPPORTED_FORMS:
            raise FetchError(
                f"Unsupported form type: {form_type}",
                details=f"Supported forms: {', '.join(SUPPORTED_FORMS)}",
            )
        return normalised

    def _parse_filing_date(self, date_value: str | date) -> date:
        """
        Parse filing date from edgartools.

        edgartools may return dates as strings or date objects depending
        on the version. This method handles both cases.

        Args:
            date_value: Filing date as string (YYYY-MM-DD) or date object.

        Returns:
            Python date object.
        """
        if isinstance(date_value, date):
            return date_value
        return datetime.strptime(date_value, "%Y-%m-%d").date()

    def _format_date_filter(
        self,
        start_date: str | date | None,
        end_date: str | date | None,
    ) -> str | None:
        """
        Format date range for edgartools filing_date parameter.

        edgartools accepts date ranges in format: "YYYY-MM-DD:YYYY-MM-DD"
        For open-ended ranges: "YYYY-MM-DD:" or ":YYYY-MM-DD"

        Args:
            start_date: Range start (inclusive), or None for open start
            end_date: Range end (inclusive), or None for open end

        Returns:
            Formatted date range string, or None if no dates specified.
        """
        if start_date is None and end_date is None:
            return None

        start_str = ""
        end_str = ""

        if start_date is not None:
            if isinstance(start_date, date):
                start_str = start_date.isoformat()
            else:
                start_str = start_date

        if end_date is not None:
            if isinstance(end_date, date):
                end_str = end_date.isoformat()
            else:
                end_str = end_date

        return f"{start_str}:{end_str}"

    def _get_company(self, ticker: str) -> Company:
        """
        Get Company object for ticker with error handling.

        Args:
            ticker: Stock ticker symbol

        Returns:
            edgartools Company object

        Raises:
            FetchError: If ticker is invalid
        """
        try:
            return Company(ticker.upper())
        except Exception as e:
            raise FetchError(
                f"Invalid ticker symbol: {ticker}",
                details=str(e),
            ) from e

    def _get_filings(
        self,
        company: Company,
        form_type: str,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ):
        """
        Get filings from company with optional filters.

        Args:
            company: edgartools Company object
            form_type: SEC form type
            year: Year filter (single, list, or range)
            start_date: Date range start
            end_date: Date range end

        Returns:
            edgartools Filings object

        Raises:
            FetchError: If no filings found
        """
        # Build filter arguments
        kwargs: dict = {"form": form_type}

        # Add year filter if specified
        if year is not None:
            if isinstance(year, range):
                kwargs["year"] = list(year)
            else:
                kwargs["year"] = year

        # Add date range filter if specified
        date_filter = self._format_date_filter(start_date, end_date)
        if date_filter is not None:
            kwargs["filing_date"] = date_filter

        logger.debug("Fetching filings with filters: %s", kwargs)

        try:
            filings = company.get_filings(**kwargs)

            if not filings or len(filings) == 0:
                filter_desc = []
                if year:
                    filter_desc.append(f"year={year}")
                if date_filter:
                    filter_desc.append(f"date={date_filter}")
                filter_str = ", ".join(filter_desc) if filter_desc else "no filters"

                raise FetchError(
                    f"No {form_type} filings found ({filter_str})",
                    details="Try adjusting your filter criteria.",
                )

            return filings

        except FetchError:
            raise
        except Exception as e:
            raise FetchError(
                f"Failed to retrieve filings",
                details=str(e),
            ) from e

    def _fetch_filing_content(
        self,
        filing,
        ticker: str,
        form_type: str,
    ) -> tuple[FilingIdentifier, str]:
        """
        Fetch HTML content for a single filing.

        Args:
            filing: edgartools Filing object
            ticker: Stock ticker symbol
            form_type: SEC form type

        Returns:
            Tuple of (FilingIdentifier, html_content)

        Raises:
            FetchError: If content fetch fails
        """
        try:
            html_content = filing.html()

            if not html_content:
                raise FetchError(
                    "Empty HTML content received",
                    details=f"Filing {filing.accession_no} returned no content.",
                )

            filing_id = FilingIdentifier(
                ticker=ticker.upper(),
                form_type=form_type,
                filing_date=self._parse_filing_date(filing.filing_date),
                accession_number=filing.accession_no,
            )

            return filing_id, html_content

        except FetchError:
            raise
        except Exception as e:
            raise FetchError(
                f"Failed to fetch content for {filing.accession_no}",
                details=str(e),
            ) from e

    # =========================================================================
    # Public Methods
    # =========================================================================

    def list_available(
        self,
        ticker: str,
        form_type: str = "10-K",
        *,
        count: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> list[FilingInfo]:
        """
        List available filings without downloading content.

        Use this method to preview what filings are available before
        downloading. This is useful for showing users what will be
        fetched or for selecting specific filings.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            form_type: SEC form type ("10-K" or "10-Q")
            count: Maximum number of filings to list (default: max_filings)
            year: Filter by year (single int, list, or range)
            start_date: Filter by date range start (YYYY-MM-DD or date)
            end_date: Filter by date range end (YYYY-MM-DD or date)

        Returns:
            List of FilingInfo objects with filing metadata

        Raises:
            FetchError: If ticker is invalid or no filings found

        Example:
            >>> available = fetcher.list_available("AAPL", "10-K", count=10)
            >>> for info in available:
            ...     print(f"{info.filing_date}: {info.accession_number}")
        """
        form_type = self._validate_form_type(form_type)
        ticker = ticker.upper()

        # Default to max_filings if count not specified
        if count is None:
            count = self.max_filings

        company = self._get_company(ticker)
        filings = self._get_filings(
            company, form_type, year=year, start_date=start_date, end_date=end_date
        )

        # Limit results
        filings_list = list(filings)[:count]

        result = []
        for filing in filings_list:
            result.append(
                FilingInfo(
                    ticker=ticker,
                    form_type=form_type,
                    filing_date=self._parse_filing_date(filing.filing_date),
                    accession_number=filing.accession_no,
                    company_name=getattr(filing, "company", ticker),
                )
            )

        logger.info(
            "Listed %d available %s filings for %s",
            len(result),
            form_type,
            ticker,
        )

        return result

    def fetch_latest(
        self,
        ticker: str,
        form_type: str = "10-K",
    ) -> tuple[FilingIdentifier, str]:
        """
        Fetch the most recent filing for a company.

        This is a convenience method equivalent to fetch_one(ticker, form, index=0).

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL", "MSFT")
            form_type: SEC form type ("10-K" or "10-Q")

        Returns:
            Tuple of (FilingIdentifier, html_content)

        Raises:
            FetchError: If ticker is invalid, no filings found, or fetch fails

        Example:
            >>> filing_id, html = fetcher.fetch_latest("NVDA", "10-Q")
            >>> print(f"Fetched: {filing_id.date_str}, {len(html):,} chars")
        """
        return self.fetch_one(ticker, form_type, index=0)

    def fetch_one(
        self,
        ticker: str,
        form_type: str = "10-K",
        *,
        index: int = 0,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> tuple[FilingIdentifier, str]:
        """
        Fetch a single filing by index position.

        Index 0 is the most recent filing, index 1 is the second most
        recent, and so on. Filters are applied before indexing.

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type ("10-K" or "10-Q")
            index: Position in filtered results (0=most recent)
            year: Filter by year before selecting index
            start_date: Filter by date range start
            end_date: Filter by date range end

        Returns:
            Tuple of (FilingIdentifier, html_content)

        Raises:
            FetchError: If index out of range or fetch fails

        Example:
            >>> # Get the third most recent 10-K
            >>> filing_id, html = fetcher.fetch_one("AAPL", "10-K", index=2)

            >>> # Get the most recent 10-K from 2023
            >>> filing_id, html = fetcher.fetch_one("AAPL", "10-K", year=2023)
        """
        form_type = self._validate_form_type(form_type)
        ticker = ticker.upper()

        logger.info(
            "Fetching %s %s at index %d",
            ticker,
            form_type,
            index,
        )

        company = self._get_company(ticker)
        filings = self._get_filings(
            company, form_type, year=year, start_date=start_date, end_date=end_date
        )

        filings_list = list(filings)

        if index >= len(filings_list):
            raise FetchError(
                f"Index {index} out of range",
                details=f"Only {len(filings_list)} filings available.",
            )

        filing = filings_list[index]
        filing_id, html_content = self._fetch_filing_content(filing, ticker, form_type)

        logger.info(
            "Fetched %s %s (%s): %s characters",
            ticker,
            form_type,
            filing_id.date_str,
            f"{len(html_content):,}",
        )

        return filing_id, html_content

    def fetch(
        self,
        ticker: str,
        form_type: str = "10-K",
        *,
        count: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> Iterator[tuple[FilingIdentifier, str]]:
        """
        Fetch multiple filings with flexible filtering.

        This is the main method for batch fetching. It returns a generator
        that yields filings one at a time, allowing incremental processing.

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type ("10-K" or "10-Q")
            count: Maximum number of filings (default: max_filings setting)
            year: Filter by year - accepts:
                  - Single int: year=2023
                  - List: year=[2022, 2023, 2024]
                  - Range: year=range(2020, 2025)
            start_date: Date range start (YYYY-MM-DD string or date object)
            end_date: Date range end (YYYY-MM-DD string or date object)

        Yields:
            Tuples of (FilingIdentifier, html_content)

        Raises:
            FetchError: If ticker is invalid or no filings match filters

        Examples:
            >>> # Last 5 filings
            >>> for fid, html in fetcher.fetch("AAPL", "10-K", count=5):
            ...     print(f"Processing {fid.date_str}")

            >>> # All 10-Ks from 2020-2024
            >>> for fid, html in fetcher.fetch("AAPL", "10-K", year=range(2020, 2025)):
            ...     print(f"Processing {fid.date_str}")

            >>> # Filings since 2022
            >>> for fid, html in fetcher.fetch("MSFT", "10-Q", start_date="2022-01-01"):
            ...     print(f"Processing {fid.date_str}")
        """
        form_type = self._validate_form_type(form_type)
        ticker = ticker.upper()

        # Default to max_filings if count not specified
        if count is None:
            count = self.max_filings

        logger.info(
            "Fetching up to %d %s filings for %s",
            count,
            form_type,
            ticker,
        )

        company = self._get_company(ticker)
        filings = self._get_filings(
            company, form_type, year=year, start_date=start_date, end_date=end_date
        )

        # Limit to requested count
        filings_list = list(filings)[:count]
        total_available = len(list(filings))

        if total_available > count:
            logger.info(
                "Limiting to %d of %d available filings",
                count,
                total_available,
            )

        fetched_count = 0
        for filing in filings_list:
            try:
                filing_id, html_content = self._fetch_filing_content(
                    filing, ticker, form_type
                )
                fetched_count += 1
                logger.debug(
                    "Fetched %d/%d: %s",
                    fetched_count,
                    len(filings_list),
                    filing_id.accession_number,
                )
                yield filing_id, html_content

            except FetchError as e:
                logger.warning(
                    "Skipping filing %s: %s",
                    filing.accession_no,
                    e.message,
                )
                continue

        logger.info(
            "Completed: fetched %d %s filings for %s",
            fetched_count,
            form_type,
            ticker,
        )

    def fetch_by_accession(
        self,
        ticker: str,
        form_type: str,
        accession_number: str,
    ) -> tuple[FilingIdentifier, str]:
        """
        Fetch a specific filing by its accession number.

        Use this method when you know the exact accession number of the
        filing you want. This is useful for re-fetching a specific filing
        or when the user has selected from list_available().

        Args:
            ticker: Stock ticker symbol
            form_type: SEC form type ("10-K" or "10-Q")
            accession_number: SEC accession number (e.g., "0000320193-23-000077")

        Returns:
            Tuple of (FilingIdentifier, html_content)

        Raises:
            FetchError: If filing not found or fetch fails

        Example:
            >>> filing_id, html = fetcher.fetch_by_accession(
            ...     "AAPL", "10-K", "0000320193-23-000077"
            ... )
        """
        form_type = self._validate_form_type(form_type)
        ticker = ticker.upper()

        logger.info(
            "Fetching %s %s by accession: %s",
            ticker,
            form_type,
            accession_number,
        )

        company = self._get_company(ticker)
        filings = self._get_filings(company, form_type)

        # Search for matching accession number
        for filing in filings:
            if filing.accession_no == accession_number:
                filing_id, html_content = self._fetch_filing_content(
                    filing, ticker, form_type
                )
                logger.info(
                    "Fetched %s %s (%s): %s characters",
                    ticker,
                    form_type,
                    filing_id.date_str,
                    f"{len(html_content):,}",
                )
                return filing_id, html_content

        raise FetchError(
            f"Filing not found: {accession_number}",
            details=f"No {form_type} filing with this accession number for {ticker}.",
        )

    # =========================================================================
    # Batch Methods (Multiple Companies)
    # =========================================================================

    def list_available_batch(
        self,
        tickers: list[str],
        form_type: str = "10-K",
        *,
        count_per_ticker: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> dict[str, list[FilingInfo]]:
        """
        List available filings for multiple companies.

        Args:
            tickers: List of stock ticker symbols
            form_type: SEC form type ("10-K" or "10-Q")
            count_per_ticker: Max filings per company (default: max_filings)
            year: Filter by year (single int, list, or range)
            start_date: Filter by date range start
            end_date: Filter by date range end

        Returns:
            Dictionary mapping ticker to list of FilingInfo objects.
            Failed tickers are included with empty lists.

        Example:
            >>> available = fetcher.list_available_batch(
            ...     ['AAPL', 'MSFT', 'GOOGL'],
            ...     '10-K',
            ...     year=range(2022, 2025)
            ... )
            >>> for ticker, filings in available.items():
            ...     print(f"{ticker}: {len(filings)} filings")
        """
        if count_per_ticker is None:
            count_per_ticker = self.max_filings

        results: dict[str, list[FilingInfo]] = {}

        logger.info(
            "Listing available %s filings for %d companies",
            form_type,
            len(tickers),
        )

        for ticker in tickers:
            try:
                filings = self.list_available(
                    ticker,
                    form_type,
                    count=count_per_ticker,
                    year=year,
                    start_date=start_date,
                    end_date=end_date,
                )
                results[ticker.upper()] = filings
            except FetchError as e:
                logger.warning("Failed to list filings for %s: %s", ticker, e.message)
                results[ticker.upper()] = []

        total_filings = sum(len(f) for f in results.values())
        logger.info(
            "Listed %d total filings across %d companies",
            total_filings,
            len(tickers),
        )

        return results

    def fetch_batch(
        self,
        tickers: list[str],
        form_type: str = "10-K",
        *,
        count_per_ticker: int | None = None,
        year: int | list[int] | range | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> Iterator[tuple[FilingIdentifier, str]]:
        """
        Fetch filings for multiple companies.

        This method iterates through multiple tickers and yields filings
        one at a time. Useful for batch ingestion operations.

        Args:
            tickers: List of stock ticker symbols
            form_type: SEC form type ("10-K" or "10-Q")
            count_per_ticker: Max filings per company (default: max_filings)
            year: Filter by year (single int, list, or range)
            start_date: Filter by date range start
            end_date: Filter by date range end

        Yields:
            Tuples of (FilingIdentifier, html_content)

        Note:
            Failed tickers are logged and skipped (no exception raised).
            The total number of filings is limited by max_filings setting
            multiplied by number of tickers.

        Example:
            >>> # Get last 2 years of 10-K for multiple companies
            >>> tickers = ['AAPL', 'AMZN', 'GOOGL', 'META']
            >>> for fid, html in fetcher.fetch_batch(
            ...     tickers, '10-K', year=range(2023, 2025)
            ... ):
            ...     print(f"Processing {fid.ticker} {fid.date_str}")
        """
        if count_per_ticker is None:
            count_per_ticker = self.max_filings

        logger.info(
            "Batch fetching %s filings for %d companies (max %d each)",
            form_type,
            len(tickers),
            count_per_ticker,
        )

        total_fetched = 0
        for ticker in tickers:
            try:
                ticker_count = 0
                for filing_id, html_content in self.fetch(
                    ticker,
                    form_type,
                    count=count_per_ticker,
                    year=year,
                    start_date=start_date,
                    end_date=end_date,
                ):
                    ticker_count += 1
                    total_fetched += 1
                    yield filing_id, html_content

                logger.debug(
                    "Fetched %d filings for %s",
                    ticker_count,
                    ticker,
                )

            except FetchError as e:
                logger.warning(
                    "Skipping %s due to error: %s",
                    ticker,
                    e.message,
                )
                continue

        logger.info(
            "Batch complete: fetched %d total %s filings",
            total_fetched,
            form_type,
        )
