"""
Logging configuration for SEC-SemanticSearch.

This module provides a consistent logging setup across all package modules.
It uses Rich for beautiful console output when running interactively.

Configuration:
    LOG_LEVEL environment variable controls the logging level.
    Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)

Usage:
    from sec_semantic_search.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Processing filing", extra={"ticker": "AAPL"})
"""

import logging
import os
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Package-level logger name
LOGGER_NAME = "sec_semantic_search"

# Default format for non-Rich handlers (e.g., file output)
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Track whether logging has been configured
_logging_configured = False


def _get_log_level() -> int:
    """
    Get log level from environment variable.

    Returns:
        Logging level constant (e.g., logging.INFO)
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def configure_logging(
    level: Optional[int] = None,
    use_rich: bool = True,
) -> None:
    """
    Configure the package-level logger.

    This function sets up the root logger for the sec_semantic_search package.
    It should be called once at application startup (e.g., in CLI main).

    Args:
        level: Logging level. If None, reads from LOG_LEVEL env var.
        use_rich: Whether to use RichHandler for console output.
                  Set to False when output is being piped or redirected.
    """
    global _logging_configured

    if _logging_configured:
        return

    log_level = level if level is not None else _get_log_level()

    # Get the package-level logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)

    # Remove any existing handlers
    logger.handlers.clear()

    # Determine if we should use Rich (interactive terminal)
    is_interactive = sys.stdout.isatty() and use_rich

    if is_interactive:
        # Rich handler for beautiful console output
        console = Console(stderr=True)
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        # Standard handler for non-interactive environments
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT)
        )

    handler.setLevel(log_level)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for the specified module.

    This function returns a child logger of the package-level logger.
    If logging hasn't been configured yet, it will be configured with
    default settings.

    Args:
        name: Module name, typically __name__ from the calling module.
              If the name doesn't start with the package name, it will
              be prefixed automatically.

    Returns:
        Configured logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing filing for %s", ticker)
    """
    # Ensure logging is configured
    if not _logging_configured:
        configure_logging()

    # Ensure the logger is under our package namespace
    if not name.startswith(LOGGER_NAME):
        name = f"{LOGGER_NAME}.{name}"

    return logging.getLogger(name)


def suppress_third_party_loggers() -> None:
    """
    Suppress verbose logging from third-party libraries.

    Some libraries (sentence-transformers, chromadb, httpx) are quite
    verbose at INFO level. This function sets them to WARNING.
    """
    noisy_loggers = [
        "sentence_transformers",
        "chromadb",
        "httpx",
        "httpcore",
        "urllib3",
        "transformers",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
