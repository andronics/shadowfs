#!/usr/bin/env python3
"""Structured logging system for ShadowFS.

This module provides a structured logging system with:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Structured context (key-value pairs)
- Multiple output handlers (console, file, syslog)
- Thread-local context management
- File rotation support

Example:
    >>> logger = Logger(level=LogLevel.INFO)
    >>> logger.info("Starting server", port=8080, host="localhost")
    >>> with logger.add_context(request_id="123"):
    ...     logger.debug("Processing request")
"""

import logging
import logging.handlers
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Union

from shadowfs.foundation.constants import ErrorCode


class LogLevel(IntEnum):
    """Log levels matching Python's logging module."""

    DEBUG = logging.DEBUG  # 10
    INFO = logging.INFO  # 20
    WARNING = logging.WARNING  # 30
    ERROR = logging.ERROR  # 40
    CRITICAL = logging.CRITICAL  # 50


@dataclass
class LogRecord:
    """Structured log record with context."""

    timestamp: datetime
    level: LogLevel
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Exception] = None


class Logger:
    """Structured logger with context support.

    Provides structured logging with key-value context that can be
    attached to log messages. Supports multiple output handlers and
    thread-local context management.
    """

    # Thread-local storage for context
    _context_stack = threading.local()

    def __init__(
        self,
        name: str = "shadowfs",
        level: Union[LogLevel, str] = LogLevel.INFO,
        handlers: Optional[List[logging.Handler]] = None,
    ):
        """Initialize logger.

        Args:
            name: Logger name for identification
            level: Minimum log level to output
            handlers: Optional list of logging handlers
        """
        self.name = name
        self.logger = logging.getLogger(name)

        # Set level
        if isinstance(level, str):
            level = LogLevel[level.upper()]
        self.set_level(level)

        # Configure handlers if not provided
        if handlers is None:
            handlers = [self._create_console_handler()]

        # Clear existing handlers and add new ones
        self.logger.handlers.clear()
        for handler in handlers:
            self.logger.addHandler(handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def _create_console_handler(self) -> logging.StreamHandler:
        """Create default console handler with formatting.

        Returns:
            Configured console handler
        """
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        return handler

    def create_file_handler(
        self,
        filename: Union[str, Path],
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ) -> logging.handlers.RotatingFileHandler:
        """Create rotating file handler.

        Args:
            filename: Path to log file
            max_bytes: Maximum size before rotation
            backup_count: Number of backup files to keep

        Returns:
            Configured rotating file handler
        """
        handler = logging.handlers.RotatingFileHandler(
            filename, maxBytes=max_bytes, backupCount=backup_count
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(context)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        return handler

    def add_handler(self, handler: logging.Handler) -> None:
        """Add a new output handler.

        Args:
            handler: Logging handler to add
        """
        self.logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler) -> None:
        """Remove an output handler.

        Args:
            handler: Logging handler to remove
        """
        self.logger.removeHandler(handler)

    def set_level(self, level: Union[LogLevel, str]) -> None:
        """Set the minimum log level.

        Args:
            level: New log level (LogLevel or string)
        """
        if isinstance(level, str):
            level = LogLevel[level.upper()]
        self.logger.setLevel(level)

    def get_level(self) -> LogLevel:
        """Get current log level.

        Returns:
            Current log level
        """
        return LogLevel(self.logger.level)

    def _get_context(self) -> Dict[str, Any]:
        """Get current thread-local context.

        Returns:
            Combined context from all levels
        """
        if not hasattr(self._context_stack, "stack"):
            self._context_stack.stack = [{}]

        # Merge all context levels
        context = {}
        for ctx in self._context_stack.stack:
            context.update(ctx)
        return context

    def _format_message(self, msg: str, context: Dict[str, Any]) -> str:
        """Format message with context.

        Args:
            msg: Log message
            context: Context dictionary

        Returns:
            Formatted message with context
        """
        if context:
            ctx_str = " ".join(f"{k}={v}" for k, v in context.items())
            return f"{msg} | {ctx_str}"
        return msg

    @contextmanager
    def add_context(self, **kwargs):
        """Context manager to add temporary context.

        Args:
            **kwargs: Key-value pairs to add to context

        Example:
            >>> with logger.add_context(request_id="123", user="admin"):
            ...     logger.info("Processing request")
        """
        if not hasattr(self._context_stack, "stack"):
            self._context_stack.stack = [{}]

        # Push new context
        self._context_stack.stack.append(kwargs)
        try:
            yield
        finally:
            # Pop context
            self._context_stack.stack.pop()

    def debug(self, msg: str, **context) -> None:
        """Log debug message.

        Args:
            msg: Log message
            **context: Additional context key-value pairs
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            combined_context = self._get_context()
            combined_context.update(context)
            formatted_msg = self._format_message(msg, combined_context)
            self.logger.debug(formatted_msg, extra={"context": combined_context})

    def info(self, msg: str, **context) -> None:
        """Log info message.

        Args:
            msg: Log message
            **context: Additional context key-value pairs
        """
        if self.logger.isEnabledFor(logging.INFO):
            combined_context = self._get_context()
            combined_context.update(context)
            formatted_msg = self._format_message(msg, combined_context)
            self.logger.info(formatted_msg, extra={"context": combined_context})

    def warning(self, msg: str, **context) -> None:
        """Log warning message.

        Args:
            msg: Log message
            **context: Additional context key-value pairs
        """
        if self.logger.isEnabledFor(logging.WARNING):
            combined_context = self._get_context()
            combined_context.update(context)
            formatted_msg = self._format_message(msg, combined_context)
            self.logger.warning(formatted_msg, extra={"context": combined_context})

    def error(self, msg: str, **context) -> None:
        """Log error message.

        Args:
            msg: Log message
            **context: Additional context key-value pairs
        """
        if self.logger.isEnabledFor(logging.ERROR):
            combined_context = self._get_context()
            combined_context.update(context)
            formatted_msg = self._format_message(msg, combined_context)
            self.logger.error(formatted_msg, extra={"context": combined_context})

    def exception(self, msg: str, exc: Exception, **context) -> None:
        """Log exception with traceback.

        Args:
            msg: Log message
            exc: Exception to log
            **context: Additional context key-value pairs
        """
        combined_context = self._get_context()
        combined_context.update(context)
        combined_context["exception_type"] = type(exc).__name__
        combined_context["exception_message"] = str(exc)
        formatted_msg = self._format_message(msg, combined_context)
        self.logger.exception(formatted_msg, exc_info=exc, extra={"context": combined_context})

    def is_enabled_for(self, level: Union[LogLevel, str]) -> bool:
        """Check if logger is enabled for given level.

        Args:
            level: Log level to check

        Returns:
            True if logger would output at this level
        """
        if isinstance(level, str):
            level = LogLevel[level.upper()]
        return self.logger.isEnabledFor(level)


# Global logger instance
_global_logger: Optional[Logger] = None


def get_logger(name: str = "shadowfs") -> Logger:
    """Get or create a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    global _global_logger
    if _global_logger is None or _global_logger.name != name:
        _global_logger = Logger(name=name)
    return _global_logger


def set_global_logger(logger: Logger) -> None:
    """Set the global logger instance.

    Args:
        logger: Logger to use globally
    """
    global _global_logger
    _global_logger = logger