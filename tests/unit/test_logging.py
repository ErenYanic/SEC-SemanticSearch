"""
Tests for the logging configuration module.

The logging module has non-trivial state: a global _logging_configured
flag, automatic namespace prefixing, and third-party logger suppression.
We reset the global flag between tests to ensure isolation.
"""

import logging

import pytest

import sec_semantic_search.core.logging as log_module
from sec_semantic_search.core.logging import (
    LOGGER_NAME,
    _get_log_level,
    configure_logging,
    get_logger,
    redact_for_log,
    suppress_third_party_loggers,
)


@pytest.fixture(autouse=True)
def reset_logging_state():
    """
    Reset the module's global _logging_configured flag between tests.

    Without this, configure_logging() would short-circuit after the
    first test that calls it, making subsequent tests unreliable.
    """
    log_module._logging_configured = False
    # Also clean up any handlers added during tests
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    yield
    log_module._logging_configured = False
    logger.handlers.clear()


class TestGetLogLevel:
    """_get_log_level() reads LOG_LEVEL from the environment."""

    def test_default_is_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert _get_log_level() == logging.INFO

    def test_reads_debug(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert _get_log_level() == logging.DEBUG

    def test_reads_warning(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        assert _get_log_level() == logging.WARNING

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        assert _get_log_level() == logging.DEBUG

    def test_invalid_falls_back_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "NONSENSE")
        assert _get_log_level() == logging.INFO


class TestConfigureLogging:
    """configure_logging() sets up the package logger."""

    def test_creates_handler(self):
        configure_logging(level=logging.DEBUG, use_rich=False)
        logger = logging.getLogger(LOGGER_NAME)
        assert len(logger.handlers) == 1

    def test_sets_level(self):
        configure_logging(level=logging.WARNING, use_rich=False)
        logger = logging.getLogger(LOGGER_NAME)
        assert logger.level == logging.WARNING

    def test_idempotent(self):
        """Calling twice should not add a second handler."""
        configure_logging(level=logging.INFO, use_rich=False)
        configure_logging(level=logging.DEBUG, use_rich=False)
        logger = logging.getLogger(LOGGER_NAME)
        assert len(logger.handlers) == 1

    def test_no_propagation(self):
        """Logger should not propagate to root to avoid duplicate output."""
        configure_logging(level=logging.INFO, use_rich=False)
        logger = logging.getLogger(LOGGER_NAME)
        assert logger.propagate is False


class TestGetLogger:
    """get_logger() returns namespaced child loggers."""

    def test_prefixes_bare_name(self):
        logger = get_logger("mymodule")
        assert logger.name == f"{LOGGER_NAME}.mymodule"

    def test_preserves_full_name(self):
        """Names already under the package namespace should not be double-prefixed."""
        logger = get_logger(f"{LOGGER_NAME}.pipeline.fetch")
        assert logger.name == f"{LOGGER_NAME}.pipeline.fetch"

    def test_auto_configures(self):
        """get_logger() should trigger configure_logging() if not yet called."""
        assert log_module._logging_configured is False
        get_logger("test")
        assert log_module._logging_configured is True

    def test_returns_logging_logger(self):
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)


class TestRedactForLog:
    """redact_for_log() hides sensitive text when LOG_REDACT_QUERIES is set."""

    def test_returns_original_when_disabled(self, monkeypatch):
        monkeypatch.delenv("LOG_REDACT_QUERIES", raising=False)
        assert redact_for_log("revenue growth forecast") == "revenue growth forecast"

    def test_returns_original_when_empty(self, monkeypatch):
        monkeypatch.setenv("LOG_REDACT_QUERIES", "")
        assert redact_for_log("secret query") == "secret query"

    @pytest.mark.parametrize("flag", ["1", "true", "yes", "TRUE", "Yes"])
    def test_redacts_when_enabled(self, monkeypatch, flag):
        monkeypatch.setenv("LOG_REDACT_QUERIES", flag)
        result = redact_for_log("revenue growth forecast")
        assert result.startswith("<redacted:")
        assert result.endswith(">")
        assert "revenue" not in result

    def test_deterministic_hash(self, monkeypatch):
        """Same input always produces the same redacted output."""
        monkeypatch.setenv("LOG_REDACT_QUERIES", "true")
        a = redact_for_log("same query")
        b = redact_for_log("same query")
        assert a == b

    def test_different_inputs_different_hashes(self, monkeypatch):
        monkeypatch.setenv("LOG_REDACT_QUERIES", "true")
        a = redact_for_log("query one")
        b = redact_for_log("query two")
        assert a != b

    def test_hash_format_is_8_hex_chars(self, monkeypatch):
        monkeypatch.setenv("LOG_REDACT_QUERIES", "1")
        result = redact_for_log("test")
        # Format: <redacted:XXXXXXXX>
        import re

        assert re.match(r"^<redacted:[0-9a-f]{8}>$", result)

    def test_false_values_do_not_redact(self, monkeypatch):
        """Values like '0', 'false', 'no' should not trigger redaction."""
        for val in ("0", "false", "no", "FALSE"):
            monkeypatch.setenv("LOG_REDACT_QUERIES", val)
            assert redact_for_log("visible") == "visible"


class TestSuppressThirdParty:
    """suppress_third_party_loggers() silences noisy libraries."""

    def test_sets_warning_level(self):
        suppress_third_party_loggers()
        for name in ["sentence_transformers", "chromadb", "httpx", "httpcore"]:
            assert logging.getLogger(name).level == logging.WARNING

    def test_idempotent(self):
        """Calling twice should not cause errors."""
        suppress_third_party_loggers()
        suppress_third_party_loggers()
        assert logging.getLogger("chromadb").level == logging.WARNING
