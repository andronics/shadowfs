#!/usr/bin/env python3
"""Additional tests for complete Logger coverage."""

import logging
from unittest.mock import MagicMock

import pytest

from shadowfs.infrastructure.logger import Logger, LogLevel, get_logger, set_global_logger


class TestMissingCoverage:
    """Tests for missing coverage lines."""

    def test_format_message_context_order(self):
        """Test that context is formatted in consistent order."""
        logger = Logger(name="test")
        # Test with multiple context items - Python 3.7+ preserves dict order
        formatted = logger._format_message("Message", {"z": 1, "a": 2, "m": 3})
        # Should preserve insertion order
        assert formatted == "Message | z=1 a=2 m=3"

    def test_debug_logging_when_disabled(self):
        """Test debug logging when level is higher than DEBUG."""
        logger = Logger(name="test", level=LogLevel.INFO)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.INFO
        logger.logger.handlers = [mock_handler]

        # Debug should not be logged when level is INFO
        logger.debug("This should not be logged")
        mock_handler.handle.assert_not_called()

    def test_info_logging_when_disabled(self):
        """Test info logging when level is higher than INFO."""
        logger = Logger(name="test", level=LogLevel.WARNING)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.WARNING
        logger.logger.handlers = [mock_handler]

        # Info should not be logged when level is WARNING
        logger.info("This should not be logged")
        mock_handler.handle.assert_not_called()

    def test_warning_logging_when_disabled(self):
        """Test warning logging when level is higher than WARNING."""
        logger = Logger(name="test", level=LogLevel.ERROR)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.ERROR
        logger.logger.handlers = [mock_handler]

        # Warning should not be logged when level is ERROR
        logger.warning("This should not be logged")
        mock_handler.handle.assert_not_called()

    def test_error_logging_when_disabled(self):
        """Test error logging when level is higher than ERROR."""
        logger = Logger(name="test", level=LogLevel.CRITICAL)
        mock_handler = MagicMock(spec=logging.Handler)
        mock_handler.level = logging.CRITICAL
        logger.logger.handlers = [mock_handler]

        # Error should not be logged when level is CRITICAL
        logger.error("This should not be logged")
        mock_handler.handle.assert_not_called()

    def test_get_logger_with_none_global(self):
        """Test get_logger when global logger is None."""
        set_global_logger(None)
        logger = get_logger()  # Default name is "shadowfs"
        assert logger.name == "shadowfs"
        assert isinstance(logger, Logger)

    def test_global_logger_lifecycle(self):
        """Test complete global logger lifecycle."""
        # Start with None
        set_global_logger(None)

        # Create first logger
        logger1 = get_logger("app1")
        assert logger1.name == "app1"

        # Get same logger again
        logger2 = get_logger("app1")
        assert logger1 is logger2

        # Get different logger
        logger3 = get_logger("app2")
        assert logger3.name == "app2"
        assert logger3 is not logger1

        # The global is now app2
        logger4 = get_logger("app2")
        assert logger4 is logger3