#!/usr/bin/env python3
"""Compression transformation.

This module provides compression/decompression transforms:
- gzip compression
- bz2 compression
- lzma compression
- Automatic format detection

Example:
    >>> transform = CompressionTransform(algorithm="gzip")
    >>> result = transform.apply(b"Hello World!", "file.txt.gz")
"""

import bz2
import gzip
import lzma
from enum import Enum
from typing import Any, Dict, Optional

from shadowfs.transforms.base import Transform, TransformError


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""

    GZIP = "gzip"
    BZ2 = "bz2"
    LZMA = "lzma"


class CompressionMode(Enum):
    """Compression or decompression mode."""

    COMPRESS = "compress"
    DECOMPRESS = "decompress"


class CompressionTransform(Transform):
    """Transform for compression/decompression.

    Supports gzip, bz2, and lzma compression algorithms.
    """

    def __init__(
        self,
        name: str = "compression",
        algorithm: str = "gzip",
        mode: str = "decompress",
        compression_level: int = 6,
        **kwargs,
    ):
        """Initialize compression transform.

        Args:
            name: Transform name
            algorithm: Compression algorithm (gzip, bz2, lzma)
            mode: compress or decompress
            compression_level: Compression level (1-9)
            **kwargs: Additional algorithm-specific options
        """
        super().__init__(name=name)

        try:
            self._algorithm = CompressionAlgorithm(algorithm.lower())
        except ValueError:
            raise TransformError(
                f"Invalid algorithm: {algorithm}. Must be gzip, bz2, or lzma",
                name,
            )

        try:
            self._mode = CompressionMode(mode.lower())
        except ValueError:
            raise TransformError(
                f"Invalid mode: {mode}. Must be compress or decompress", name
            )

        self._compression_level = max(1, min(9, compression_level))
        self._options = kwargs

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if path matches compression patterns.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True if path should be processed
        """
        # Check file extension
        if self._mode == CompressionMode.DECOMPRESS:
            # Decompress files with appropriate extensions
            if self._algorithm == CompressionAlgorithm.GZIP:
                return path.endswith(".gz")
            elif self._algorithm == CompressionAlgorithm.BZ2:
                return path.endswith(".bz2")
            elif self._algorithm == CompressionAlgorithm.LZMA:
                return path.endswith((".xz", ".lzma"))
        else:
            # Compress any file (can be limited by patterns if needed)
            return True

        return False

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Compress or decompress content.

        Args:
            content: Input content
            path: File path
            metadata: Optional metadata

        Returns:
            Transformed content

        Raises:
            TransformError: If compression/decompression fails
        """
        try:
            if self._mode == CompressionMode.COMPRESS:
                return self._compress(content)
            else:
                return self._decompress(content)

        except Exception as e:
            raise TransformError(
                f"Compression error ({self._algorithm.value}, {self._mode.value}): {e}",
                self.name,
            )

    def _compress(self, content: bytes) -> bytes:
        """Compress content.

        Args:
            content: Input content

        Returns:
            Compressed content
        """
        if self._algorithm == CompressionAlgorithm.GZIP:
            return gzip.compress(content, compresslevel=self._compression_level)
        elif self._algorithm == CompressionAlgorithm.BZ2:
            return bz2.compress(content, compresslevel=self._compression_level)
        elif self._algorithm == CompressionAlgorithm.LZMA:
            return lzma.compress(content)

        raise TransformError(f"Unknown algorithm: {self._algorithm}", self.name)

    def _decompress(self, content: bytes) -> bytes:
        """Decompress content.

        Args:
            content: Compressed content

        Returns:
            Decompressed content
        """
        if self._algorithm == CompressionAlgorithm.GZIP:
            return gzip.decompress(content)
        elif self._algorithm == CompressionAlgorithm.BZ2:
            return bz2.decompress(content)
        elif self._algorithm == CompressionAlgorithm.LZMA:
            return lzma.decompress(content)

        raise TransformError(f"Unknown algorithm: {self._algorithm}", self.name)

    def get_metadata(
        self, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get transform metadata.

        Args:
            path: File path
            metadata: Input metadata

        Returns:
            Metadata with compression info
        """
        return {
            "transform": self.name,
            "algorithm": self._algorithm.value,
            "mode": self._mode.value,
            "compression_level": self._compression_level,
        }


class AutoDecompressTransform(Transform):
    """Auto-detect compression format and decompress.

    Tries multiple decompression algorithms until one succeeds.
    """

    def __init__(self, name: str = "auto_decompress"):
        """Initialize auto-decompress transform.

        Args:
            name: Transform name
        """
        super().__init__(name=name)
        self._algorithms = [
            CompressionAlgorithm.GZIP,
            CompressionAlgorithm.BZ2,
            CompressionAlgorithm.LZMA,
        ]

    def supports(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if path might be compressed.

        Args:
            path: File path
            metadata: Optional metadata

        Returns:
            True if path might be compressed
        """
        compressed_extensions = (".gz", ".bz2", ".xz", ".lzma")
        return any(path.endswith(ext) for ext in compressed_extensions)

    def transform(
        self, content: bytes, path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Auto-detect and decompress content.

        Args:
            content: Compressed content
            path: File path
            metadata: Optional metadata

        Returns:
            Decompressed content

        Raises:
            TransformError: If all decompression attempts fail
        """
        errors = []

        for algorithm in self._algorithms:
            try:
                if algorithm == CompressionAlgorithm.GZIP:
                    return gzip.decompress(content)
                elif algorithm == CompressionAlgorithm.BZ2:
                    return bz2.decompress(content)
                elif algorithm == CompressionAlgorithm.LZMA:
                    return lzma.decompress(content)
            except Exception as e:
                errors.append(f"{algorithm.value}: {e}")
                continue

        # All algorithms failed
        error_msg = "Failed to decompress with any algorithm. Errors: " + "; ".join(
            errors
        )
        raise TransformError(error_msg, self.name)
