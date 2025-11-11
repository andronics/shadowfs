#!/usr/bin/env python3
"""Base classes for content transformations.

This module provides the foundation for all transforms:
- Transform abstract base class
- TransformResult for returning transformed content
- TransformError for error handling
- Common transform utilities

Example:
    >>> class UppercaseTransform(Transform):
    ...     def transform(self, content, path, metadata):
    ...         return content.upper()
    ...
    >>> transform = UppercaseTransform()
    >>> result = transform.apply(b"hello", "test.txt")
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TransformType(Enum):
    """Type of transformation."""

    TEMPLATE = "template"  # Template expansion
    COMPRESSION = "compression"  # Compression/decompression
    ENCRYPTION = "encryption"  # Encryption/decryption
    CONVERSION = "conversion"  # Format conversion
    CUSTOM = "custom"  # Custom transformation


@dataclass
class TransformResult:
    """Result of a transformation.

    Contains the transformed content and metadata about the transformation.
    """

    content: bytes
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    transform_name: Optional[str] = None
    duration_ms: float = 0.0


class TransformError(Exception):
    """Error during transformation."""

    def __init__(self, message: str, transform_name: Optional[str] = None):
        self.message = message
        self.transform_name = transform_name
        super().__init__(message)


class Transform(ABC):
    """Abstract base class for content transformations.

    All transforms must implement:
    - transform(): Core transformation logic
    - supports(): Check if transform applies to a path

    Optional overrides:
    - before_transform(): Pre-processing
    - after_transform(): Post-processing
    - get_metadata(): Return transform metadata
    """

    def __init__(self, name: Optional[str] = None, enabled: bool = True):
        """Initialize transform.

        Args:
            name: Optional name for this transform
            enabled: Whether transform is enabled
        """
        self.name = name or self.__class__.__name__
        self.enabled = enabled
        self._stats = {
            "total_transforms": 0,
            "successful_transforms": 0,
            "failed_transforms": 0,
            "total_duration_ms": 0.0,
        }

    @abstractmethod
    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Transform content.

        Args:
            content: Input content
            path: File path (for context)
            metadata: Optional metadata

        Returns:
            Transformed content

        Raises:
            TransformError: If transformation fails
        """
        pass

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if this transform supports the given path.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True if transform should be applied
        """
        return True

    def apply(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> TransformResult:
        """Apply transformation with error handling and timing.

        Args:
            content: Input content
            path: File path
            metadata: Optional metadata

        Returns:
            TransformResult with transformed content
        """
        if not self.enabled:
            return TransformResult(
                content=content,
                success=True,
                metadata={"skipped": True, "reason": "Transform disabled"},
                transform_name=self.name,
            )

        if not self.supports(path, metadata):
            return TransformResult(
                content=content,
                success=True,
                metadata={"skipped": True, "reason": "Path not supported"},
                transform_name=self.name,
            )

        start_time = time.time()

        try:
            # Pre-processing hook
            self.before_transform(content, path, metadata)

            # Core transformation
            transformed = self.transform(content, path, metadata)

            # Post-processing hook
            transformed = self.after_transform(transformed, path, metadata)

            duration_ms = (time.time() - start_time) * 1000

            # Update stats
            self._stats["total_transforms"] += 1
            self._stats["successful_transforms"] += 1
            self._stats["total_duration_ms"] += duration_ms

            return TransformResult(
                content=transformed,
                success=True,
                metadata=self.get_metadata(path, metadata),
                transform_name=self.name,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Update stats
            self._stats["total_transforms"] += 1
            self._stats["failed_transforms"] += 1
            self._stats["total_duration_ms"] += duration_ms

            error_msg = f"{self.name}: {str(e)}"

            return TransformResult(
                content=content,  # Return original on error
                success=False,
                error=error_msg,
                transform_name=self.name,
                duration_ms=duration_ms,
            )

    def before_transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Hook called before transformation.

        Args:
            content: Input content
            path: File path
            metadata: Optional metadata
        """
        pass

    def after_transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]]
    ) -> bytes:
        """Hook called after transformation.

        Args:
            content: Transformed content
            path: File path
            metadata: Optional metadata

        Returns:
            Content (possibly modified)
        """
        return content

    def get_metadata(
        self, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get transform metadata.

        Args:
            path: File path
            metadata: Input metadata

        Returns:
            Metadata dictionary
        """
        return {"transform": self.name}

    def get_stats(self) -> Dict[str, Any]:
        """Get transform statistics.

        Returns:
            Statistics dictionary
        """
        stats = self._stats.copy()
        if stats["total_transforms"] > 0:
            stats["avg_duration_ms"] = (
                stats["total_duration_ms"] / stats["total_transforms"]
            )
            stats["success_rate"] = (
                stats["successful_transforms"] / stats["total_transforms"]
            )
        else:
            stats["avg_duration_ms"] = 0.0
            stats["success_rate"] = 0.0

        return stats

    def reset_stats(self) -> None:
        """Reset transform statistics."""
        self._stats = {
            "total_transforms": 0,
            "successful_transforms": 0,
            "failed_transforms": 0,
            "total_duration_ms": 0.0,
        }

    def enable(self) -> None:
        """Enable this transform."""
        self.enabled = True

    def disable(self) -> None:
        """Disable this transform."""
        self.enabled = False

    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} name={self.name} {status}>"
