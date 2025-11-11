#!/usr/bin/env python3
"""Comprehensive tests for CompressionTransform."""

import bz2
import gzip
import lzma

import pytest

from shadowfs.transforms.base import TransformError
from shadowfs.transforms.compression import (
    AutoDecompressTransform,
    CompressionAlgorithm,
    CompressionMode,
    CompressionTransform,
)


class TestCompressionAlgorithm:
    """Tests for CompressionAlgorithm enum."""

    def test_gzip(self):
        """Test GZIP algorithm."""
        assert CompressionAlgorithm.GZIP.value == "gzip"

    def test_bz2(self):
        """Test BZ2 algorithm."""
        assert CompressionAlgorithm.BZ2.value == "bz2"

    def test_lzma(self):
        """Test LZMA algorithm."""
        assert CompressionAlgorithm.LZMA.value == "lzma"


class TestCompressionMode:
    """Tests for CompressionMode enum."""

    def test_compress(self):
        """Test COMPRESS mode."""
        assert CompressionMode.COMPRESS.value == "compress"

    def test_decompress(self):
        """Test DECOMPRESS mode."""
        assert CompressionMode.DECOMPRESS.value == "decompress"


class TestCompressionTransform:
    """Tests for CompressionTransform class."""

    def test_init_default(self):
        """Test default initialization."""
        transform = CompressionTransform()

        assert transform.name == "compression"
        assert transform._algorithm == CompressionAlgorithm.GZIP
        assert transform._mode == CompressionMode.DECOMPRESS
        assert transform._compression_level == 6

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        transform = CompressionTransform(
            name="my_compressor",
            algorithm="bz2",
            mode="compress",
            compression_level=9,
        )

        assert transform.name == "my_compressor"
        assert transform._algorithm == CompressionAlgorithm.BZ2
        assert transform._mode == CompressionMode.COMPRESS
        assert transform._compression_level == 9

    def test_init_invalid_algorithm(self):
        """Test initialization with invalid algorithm."""
        with pytest.raises(TransformError) as exc_info:
            CompressionTransform(algorithm="invalid")

        assert "Invalid algorithm" in str(exc_info.value)

    def test_init_invalid_mode(self):
        """Test initialization with invalid mode."""
        with pytest.raises(TransformError) as exc_info:
            CompressionTransform(mode="invalid")

        assert "Invalid mode" in str(exc_info.value)

    def test_compression_level_clamping(self):
        """Test that compression level is clamped to 1-9."""
        transform1 = CompressionTransform(compression_level=0)
        assert transform1._compression_level == 1

        transform2 = CompressionTransform(compression_level=15)
        assert transform2._compression_level == 9

    def test_supports_gzip_decompress(self):
        """Test supports for gzip decompression."""
        transform = CompressionTransform(algorithm="gzip", mode="decompress")

        assert transform.supports("file.gz") is True
        assert transform.supports("file.txt") is False

    def test_supports_bz2_decompress(self):
        """Test supports for bz2 decompression."""
        transform = CompressionTransform(algorithm="bz2", mode="decompress")

        assert transform.supports("file.bz2") is True
        assert transform.supports("file.gz") is False

    def test_supports_lzma_decompress(self):
        """Test supports for lzma decompression."""
        transform = CompressionTransform(algorithm="lzma", mode="decompress")

        assert transform.supports("file.xz") is True
        assert transform.supports("file.lzma") is True
        assert transform.supports("file.gz") is False

    def test_supports_compress_mode(self):
        """Test supports for compression mode (supports all files)."""
        transform = CompressionTransform(algorithm="gzip", mode="compress")

        assert transform.supports("file.txt") is True
        assert transform.supports("file.py") is True
        assert transform.supports("anything") is True

    def test_compress_gzip(self):
        """Test gzip compression."""
        transform = CompressionTransform(algorithm="gzip", mode="compress")
        content = b"Hello World! " * 100

        result = transform.apply(content, "file.txt")

        assert result.success is True
        assert len(result.content) < len(content)  # Compressed should be smaller
        # Verify it's valid gzip
        decompressed = gzip.decompress(result.content)
        assert decompressed == content

    def test_compress_bz2(self):
        """Test bz2 compression."""
        transform = CompressionTransform(algorithm="bz2", mode="compress")
        content = b"Hello World! " * 100

        result = transform.apply(content, "file.txt")

        assert result.success is True
        assert len(result.content) < len(content)
        # Verify it's valid bz2
        decompressed = bz2.decompress(result.content)
        assert decompressed == content

    def test_compress_lzma(self):
        """Test lzma compression."""
        transform = CompressionTransform(algorithm="lzma", mode="compress")
        content = b"Hello World! " * 100

        result = transform.apply(content, "file.txt")

        assert result.success is True
        assert len(result.content) < len(content)
        # Verify it's valid lzma
        decompressed = lzma.decompress(result.content)
        assert decompressed == content

    def test_decompress_gzip(self):
        """Test gzip decompression."""
        original = b"Hello World! " * 100
        compressed = gzip.compress(original)

        transform = CompressionTransform(algorithm="gzip", mode="decompress")
        result = transform.apply(compressed, "file.gz")

        assert result.success is True
        assert result.content == original

    def test_decompress_bz2(self):
        """Test bz2 decompression."""
        original = b"Hello World! " * 100
        compressed = bz2.compress(original)

        transform = CompressionTransform(algorithm="bz2", mode="decompress")
        result = transform.apply(compressed, "file.bz2")

        assert result.success is True
        assert result.content == original

    def test_decompress_lzma(self):
        """Test lzma decompression."""
        original = b"Hello World! " * 100
        compressed = lzma.compress(original)

        transform = CompressionTransform(algorithm="lzma", mode="decompress")
        result = transform.apply(compressed, "file.xz")

        assert result.success is True
        assert result.content == original

    def test_compression_levels(self):
        """Test different compression levels."""
        content = b"Hello World! " * 1000

        transform_low = CompressionTransform(algorithm="gzip", mode="compress", compression_level=1)
        transform_high = CompressionTransform(
            algorithm="gzip", mode="compress", compression_level=9
        )

        result_low = transform_low.apply(content, "file.txt")
        result_high = transform_high.apply(content, "file.txt")

        # Higher compression should produce smaller output
        assert len(result_high.content) <= len(result_low.content)

    def test_decompress_invalid_data(self):
        """Test decompression with invalid data."""
        transform = CompressionTransform(algorithm="gzip", mode="decompress")
        invalid_data = b"not compressed data"

        result = transform.apply(invalid_data, "file.gz")

        assert result.success is False
        assert result.error is not None
        assert "Compression error" in result.error
        # Original content returned on error
        assert result.content == invalid_data

    def test_get_metadata(self):
        """Test get_metadata."""
        transform = CompressionTransform(algorithm="gzip", mode="compress", compression_level=7)

        metadata = transform.get_metadata("file.txt")

        assert metadata["transform"] == "compression"
        assert metadata["algorithm"] == "gzip"
        assert metadata["mode"] == "compress"
        assert metadata["compression_level"] == 7

    def test_roundtrip_gzip(self):
        """Test compress then decompress with gzip."""
        original = b"The quick brown fox jumps over the lazy dog. " * 50

        # Compress
        compressor = CompressionTransform(algorithm="gzip", mode="compress")
        compressed_result = compressor.apply(original, "file.txt")

        # Decompress
        decompressor = CompressionTransform(algorithm="gzip", mode="decompress")
        decompressed_result = decompressor.apply(compressed_result.content, "file.gz")

        assert decompressed_result.content == original

    def test_roundtrip_bz2(self):
        """Test compress then decompress with bz2."""
        original = b"The quick brown fox jumps over the lazy dog. " * 50

        compressor = CompressionTransform(algorithm="bz2", mode="compress")
        compressed_result = compressor.apply(original, "file.txt")

        decompressor = CompressionTransform(algorithm="bz2", mode="decompress")
        decompressed_result = decompressor.apply(compressed_result.content, "file.bz2")

        assert decompressed_result.content == original

    def test_roundtrip_lzma(self):
        """Test compress then decompress with lzma."""
        original = b"The quick brown fox jumps over the lazy dog. " * 50

        compressor = CompressionTransform(algorithm="lzma", mode="compress")
        compressed_result = compressor.apply(original, "file.txt")

        decompressor = CompressionTransform(algorithm="lzma", mode="decompress")
        decompressed_result = decompressor.apply(compressed_result.content, "file.xz")

        assert decompressed_result.content == original

    def test_empty_content(self):
        """Test compression of empty content."""
        transform = CompressionTransform(algorithm="gzip", mode="compress")
        result = transform.apply(b"", "file.txt")

        assert result.success is True
        # Even empty content produces some compressed output (headers)
        assert len(result.content) > 0


class TestAutoDecompressTransform:
    """Tests for AutoDecompressTransform class."""

    def test_init(self):
        """Test initialization."""
        transform = AutoDecompressTransform()

        assert transform.name == "auto_decompress"
        assert len(transform._algorithms) == 3

    def test_init_custom_name(self):
        """Test initialization with custom name."""
        transform = AutoDecompressTransform(name="my_auto")

        assert transform.name == "my_auto"

    def test_supports_gzip(self):
        """Test supports for gzip files."""
        transform = AutoDecompressTransform()

        assert transform.supports("file.gz") is True

    def test_supports_bz2(self):
        """Test supports for bz2 files."""
        transform = AutoDecompressTransform()

        assert transform.supports("file.bz2") is True

    def test_supports_lzma(self):
        """Test supports for lzma files."""
        transform = AutoDecompressTransform()

        assert transform.supports("file.xz") is True
        assert transform.supports("file.lzma") is True

    def test_supports_uncompressed(self):
        """Test supports returns False for uncompressed files."""
        transform = AutoDecompressTransform()

        assert transform.supports("file.txt") is False
        assert transform.supports("file.py") is False

    def test_auto_decompress_gzip(self):
        """Test auto-decompression of gzip data."""
        original = b"Hello World! " * 100
        compressed = gzip.compress(original)

        transform = AutoDecompressTransform()
        result = transform.apply(compressed, "file.gz")

        assert result.success is True
        assert result.content == original

    def test_auto_decompress_bz2(self):
        """Test auto-decompression of bz2 data."""
        original = b"Hello World! " * 100
        compressed = bz2.compress(original)

        transform = AutoDecompressTransform()
        result = transform.apply(compressed, "file.bz2")

        assert result.success is True
        assert result.content == original

    def test_auto_decompress_lzma(self):
        """Test auto-decompression of lzma data."""
        original = b"Hello World! " * 100
        compressed = lzma.compress(original)

        transform = AutoDecompressTransform()
        result = transform.apply(compressed, "file.xz")

        assert result.success is True
        assert result.content == original

    def test_auto_decompress_invalid_data(self):
        """Test auto-decompression with invalid data."""
        transform = AutoDecompressTransform()
        invalid_data = b"not compressed data at all"

        result = transform.apply(invalid_data, "file.gz")

        assert result.success is False
        assert result.error is not None
        assert "Failed to decompress with any algorithm" in result.error
        # Original content returned on error
        assert result.content == invalid_data

    def test_auto_decompress_tries_all_algorithms(self):
        """Test that auto-decompress tries all algorithms."""
        transform = AutoDecompressTransform()

        # Create data that will fail gzip but succeed with bz2
        original = b"Test data " * 100  # Make it longer to compress better
        bz2_compressed = bz2.compress(original)

        # Give it a .gz extension to force trying gzip first
        result = transform.apply(bz2_compressed, "file.gz")

        # Should successfully decompress by trying bz2 after gzip fails
        assert result.success is True
        assert result.content == original

    def test_auto_decompress_format_mismatch(self):
        """Test auto-decompress with mismatched extension."""
        original = b"Hello World! " * 50

        # Compress with gzip but give it .bz2 extension
        gzip_data = gzip.compress(original)

        transform = AutoDecompressTransform()
        result = transform.apply(gzip_data, "file.bz2")

        # Should still work (auto-detects gzip)
        assert result.success is True
        assert result.content == original
