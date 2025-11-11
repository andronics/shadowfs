#!/usr/bin/env python3
"""Comprehensive tests for the Logger module."""

import io
import logging
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.infrastructure.logger import (
    LogLevel,
    LogRecord,
    Logger,
    get_logger,
    set_global_logger,
)


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels(self):
        """Test log level values match Python logging."""
        assert LogLevel.DEBUG == logging.DEBUG
        assert LogLevel.INFO == logging.INFO
        assert LogLevel.WARNING == logging.WARNING
        assert LogLevel.ERROR == logging.ERROR
        assert LogLevel.CRITICAL == logging.CRITICAL

    def test_log_level_ordering(self):
        """Test log levels are ordered correctly."""
        assert LogLevel.DEBUG < LogLevel.INFO
        assert LogLevel.INFO < LogLevel.WARNING
        assert LogLevel.WARNING < LogLevel.ERROR
        assert LogLevel.ERROR < LogLevel.CRITICAL


class TestLogRecord:
    """Tests for LogRecord dataclass."""

    def test_log_record_creation(self):
        """Test creating a log record."""
        from datetime import datetime

        now = datetime.now()
        record = LogRecord(
            timestamp=now,
            level=LogLevel.INFO,
            message="Test message",
            context={"key": "value"},
            exception=ValueError("test"),
        )
        assert record.timestamp == now
        assert record.level == LogLevel.INFO
        assert record.message == "Test message"
        assert record.context == {"key": "value"}
        assert isinstance(record.exception, ValueError)

    def test_log_record_defaults(self):
        """Test log record default values."""
        from datetime import datetime

        now = datetime.now()
        record = LogRecord(timestamp=now, level=LogLevel.INFO, message="Test")
        assert record.context == {}
        assert record.exception is None


class TestLogger:
    """Tests for Logger class."""

    def test_logger_creation(self):
        """Test creating a logger."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        assert logger.name == "test"
        assert logger.get_level() == LogLevel.DEBUG

    def test_logger_with_string_level(self):
        """Test creating logger with string level."""
        logger = Logger(name="test", level="WARNING")
        assert logger.get_level() == LogLevel.WARNING

    def test_logger_with_custom_handlers(self):
        """Test logger with custom handlers."""
        handler = logging.StreamHandler()
        logger = Logger(name="test", handlers=[handler])
        assert handler in logger.logger.handlers

    def test_set_level(self):
        """Test setting log level."""
        logger = Logger(name="test")
        logger.set_level(LogLevel.DEBUG)
        assert logger.get_level() == LogLevel.DEBUG

    def test_set_level_with_string(self):
        """Test setting log level with string."""
        logger = Logger(name="test")
        logger.set_level("ERROR")
        assert logger.get_level() == LogLevel.ERROR

    def test_add_handler(self):
        """Test adding a handler."""
        logger = Logger(name="test")
        handler = logging.StreamHandler()
        logger.add_handler(handler)
        assert handler in logger.logger.handlers

    def test_remove_handler(self):
        """Test removing a handler."""
        handler = logging.StreamHandler()
        logger = Logger(name="test", handlers=[handler])
        logger.remove_handler(handler)
        assert handler not in logger.logger.handlers

    def test_create_file_handler(self):
        """Test creating a file handler."""
        logger = Logger(name="test")
        with tempfile.NamedTemporaryFile(suffix=".log") as tmp:
            handler = logger.create_file_handler(
                tmp.name, max_bytes=1000, backup_count=3
            )
            assert isinstance(handler, logging.handlers.RotatingFileHandler)
            assert handler.maxBytes == 1000
            assert handler.backupCount == 3

    def test_is_enabled_for(self):
        """Test checking if logger is enabled for level."""
        logger = Logger(name="test", level=LogLevel.INFO)
        assert not logger.is_enabled_for(LogLevel.DEBUG)
        assert logger.is_enabled_for(LogLevel.INFO)
        assert logger.is_enabled_for(LogLevel.WARNING)
        assert logger.is_enabled_for(LogLevel.ERROR)

    def test_is_enabled_for_string(self):
        """Test checking if logger is enabled with string level."""
        logger = Logger(name="test", level=LogLevel.INFO)
        assert not logger.is_enabled_for("DEBUG")
        assert logger.is_enabled_for("INFO")


class TestLoggingMethods:
    """Tests for logging methods."""

    @pytest.fixture
    def logger_with_mock_handler(self):
        """Create logger with mock handler."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.DEBUG  # Add level attribute
        logger.logger.handlers.clear()
        logger.logger.addHandler(mock_handler)
        return logger, mock_handler

    def test_debug_logging(self, logger_with_mock_handler):
        """Test debug logging."""
        logger, mock_handler = logger_with_mock_handler
        logger.debug("Debug message", key="value")
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert "Debug message" in record.getMessage()
        assert "key=value" in record.getMessage()

    def test_info_logging(self, logger_with_mock_handler):
        """Test info logging."""
        logger, mock_handler = logger_with_mock_handler
        logger.info("Info message", status="ok")
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert "Info message" in record.getMessage()
        assert "status=ok" in record.getMessage()

    def test_warning_logging(self, logger_with_mock_handler):
        """Test warning logging."""
        logger, mock_handler = logger_with_mock_handler
        logger.warning("Warning message", level="high")
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert "Warning message" in record.getMessage()
        assert "level=high" in record.getMessage()

    def test_error_logging(self, logger_with_mock_handler):
        """Test error logging."""
        logger, mock_handler = logger_with_mock_handler
        logger.error("Error message", code=500)
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert "Error message" in record.getMessage()
        assert "code=500" in record.getMessage()

    def test_exception_logging(self, logger_with_mock_handler):
        """Test exception logging."""
        logger, mock_handler = logger_with_mock_handler
        exc = ValueError("Test error")
        logger.exception("Exception occurred", exc, detail="important")
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert "Exception occurred" in record.getMessage()
        assert "exception_type=ValueError" in record.getMessage()
        assert "exception_message=Test error" in record.getMessage()
        assert "detail=important" in record.getMessage()

    def test_logging_disabled_level(self, logger_with_mock_handler):
        """Test logging at disabled level."""
        logger, mock_handler = logger_with_mock_handler
        logger.set_level(LogLevel.WARNING)
        logger.debug("Debug message")
        logger.info("Info message")
        mock_handler.handle.assert_not_called()

    def test_logging_without_context(self, logger_with_mock_handler):
        """Test logging without context."""
        logger, mock_handler = logger_with_mock_handler
        logger.info("Plain message")
        mock_handler.handle.assert_called_once()
        record = mock_handler.handle.call_args[0][0]
        assert record.getMessage() == "Plain message"


class TestContextManager:
    """Tests for context manager functionality."""

    def test_add_context_basic(self):
        """Test adding context with context manager."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.DEBUG
        logger.logger.handlers = [mock_handler]

        with logger.add_context(request_id="123"):
            logger.info("In context")
            mock_handler.handle.assert_called_once()
            record = mock_handler.handle.call_args[0][0]
            assert "request_id=123" in record.getMessage()

    def test_nested_context(self):
        """Test nested context managers."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.DEBUG
        logger.logger.handlers = [mock_handler]

        with logger.add_context(outer="1"):
            with logger.add_context(inner="2"):
                logger.info("Nested")
                record = mock_handler.handle.call_args[0][0]
                msg = record.getMessage()
                assert "outer=1" in msg
                assert "inner=2" in msg

    def test_context_cleanup(self):
        """Test context is cleaned up after exiting."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.DEBUG
        logger.logger.handlers = [mock_handler]

        with logger.add_context(temp="value"):
            pass

        logger.info("After context")
        record = mock_handler.handle.call_args[0][0]
        assert "temp=value" not in record.getMessage()

    def test_context_with_exception(self):
        """Test context cleanup when exception occurs."""
        logger = Logger(name="test", level=LogLevel.DEBUG)

        try:
            with logger.add_context(error="context"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Context should be cleaned up even after exception
        context = logger._get_context()
        assert "error" not in context

    def test_thread_local_context(self):
        """Test context is thread-local."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        results = []

        def thread_func(value):
            with logger.add_context(thread_id=value):
                context = logger._get_context()
                results.append(context.get("thread_id"))

        threads = []
        for i in range(3):
            t = threading.Thread(target=thread_func, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Each thread should have seen only its own context
        assert sorted(results) == [0, 1, 2]


class TestFormattingHelpers:
    """Tests for formatting helper methods."""

    def test_format_message_with_context(self):
        """Test formatting message with context."""
        logger = Logger(name="test")
        formatted = logger._format_message("Message", {"key": "value", "num": 42})
        assert formatted == "Message | key=value num=42"

    def test_format_message_without_context(self):
        """Test formatting message without context."""
        logger = Logger(name="test")
        formatted = logger._format_message("Message", {})
        assert formatted == "Message"

    def test_get_context_uninitialized(self):
        """Test getting context when uninitialized."""
        logger = Logger(name="test")
        # Clear thread-local storage
        if hasattr(logger._context_stack, "stack"):
            delattr(logger._context_stack, "stack")
        context = logger._get_context()
        assert context == {}

    def test_get_context_with_stack(self):
        """Test getting merged context from stack."""
        logger = Logger(name="test")
        logger._context_stack.stack = [{"a": 1}, {"b": 2}, {"a": 3}]
        context = logger._get_context()
        assert context == {"a": 3, "b": 2}  # Later values override


class TestGlobalLogger:
    """Tests for global logger functions."""

    def test_get_logger_creates_instance(self):
        """Test get_logger creates new instance."""
        # Reset global
        set_global_logger(None)
        logger = get_logger("test_app")
        assert logger.name == "test_app"
        assert isinstance(logger, Logger)

    def test_get_logger_reuses_instance(self):
        """Test get_logger reuses existing instance."""
        set_global_logger(None)
        logger1 = get_logger("test_app")
        logger2 = get_logger("test_app")
        assert logger1 is logger2

    def test_get_logger_different_name(self):
        """Test get_logger creates new instance for different name."""
        set_global_logger(None)
        logger1 = get_logger("app1")
        logger2 = get_logger("app2")
        assert logger1 is not logger2
        assert logger2.name == "app2"

    def test_set_global_logger(self):
        """Test setting global logger."""
        custom_logger = Logger(name="custom", level=LogLevel.ERROR)
        set_global_logger(custom_logger)
        logger = get_logger("custom")
        assert logger is custom_logger


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_invalid_level_string(self):
        """Test invalid level string raises KeyError."""
        logger = Logger(name="test")
        with pytest.raises(KeyError):
            logger.set_level("INVALID")

    def test_propagation_disabled(self):
        """Test logger propagation is disabled."""
        logger = Logger(name="test.child")
        assert logger.logger.propagate is False

    def test_console_handler_format(self):
        """Test console handler formatting."""
        logger = Logger(name="test")
        handler = logger._create_console_handler()
        assert isinstance(handler, logging.StreamHandler)
        assert handler.formatter is not None

    def test_file_handler_with_path_object(self):
        """Test file handler with Path object."""
        logger = Logger(name="test")
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.log"
            handler = logger.create_file_handler(log_path)
            assert isinstance(handler, logging.handlers.RotatingFileHandler)

    def test_concurrent_logging(self):
        """Test concurrent logging from multiple threads."""
        logger = Logger(name="test", level=LogLevel.DEBUG)
        results = []

        def log_func(thread_id):
            for i in range(10):
                logger.info(f"Thread {thread_id} message {i}")
            results.append(thread_id)

        threads = []
        for i in range(5):
            t = threading.Thread(target=log_func, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 5


class TestIntegration:
    """Integration tests for complete logging scenarios."""

    def test_full_logging_scenario(self):
        """Test complete logging scenario with file output."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as tmp:
            log_file = tmp.name

        try:
            # Create logger with file handler
            logger = Logger(name="integration", level=LogLevel.DEBUG)
            file_handler = logger.create_file_handler(log_file, max_bytes=10000)
            logger.add_handler(file_handler)

            # Log at various levels with context
            with logger.add_context(session_id="abc123"):
                logger.debug("Starting process")
                logger.info("Processing item", item_id=1)

                with logger.add_context(user="admin"):
                    logger.warning("Low memory", available_mb=100)

                    try:
                        raise ValueError("Test error")
                    except ValueError as e:
                        logger.exception("Operation failed", e, retry_count=3)

                logger.error("Critical error", error_code=500)

            # Read and verify log file
            with open(log_file, "r") as f:
                content = f.read()
                assert "Starting process" in content
                assert "session_id=abc123" in content
                assert "user=admin" in content
                assert "ValueError" in content

        finally:
            # Cleanup
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_log_rotation(self):
        """Test log file rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            # Create logger with small max size
            logger = Logger(name="rotation", level=LogLevel.INFO)
            handler = logger.create_file_handler(
                log_file, max_bytes=100, backup_count=2
            )
            logger.add_handler(handler)

            # Write enough to trigger rotation
            for i in range(20):
                logger.info(f"Message {i} with some padding to fill space")

            # Check that backup files were created
            files = list(Path(tmpdir).glob("test.log*"))
            assert len(files) > 1  # Should have main + at least one backup