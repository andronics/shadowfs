#!/usr/bin/env python3
"""Comprehensive tests for TransformPipeline."""

import pytest

from shadowfs.transforms.base import Transform, TransformError
from shadowfs.transforms.pipeline import TransformPipeline


class UppercaseTransform(Transform):
    """Transform that uppercases content."""

    def transform(self, content, path, metadata=None):
        return content.upper()


class LowercaseTransform(Transform):
    """Transform that lowercases content."""

    def transform(self, content, path, metadata=None):
        return content.lower()


class ReverseTransform(Transform):
    """Transform that reverses content."""

    def transform(self, content, path, metadata=None):
        return content[::-1]


class FailingTransform(Transform):
    """Transform that always fails."""

    def transform(self, content, path, metadata=None):
        raise TransformError("Intentional failure", self.name)


class ConditionalTransform(Transform):
    """Transform that only supports .txt files."""

    def supports(self, path, metadata=None):
        return path.endswith(".txt")

    def transform(self, content, path, metadata=None):
        return content.upper()


class TestTransformPipeline:
    """Tests for TransformPipeline class."""

    def test_init_default(self):
        """Test default initialization."""
        pipeline = TransformPipeline()

        assert len(pipeline) == 0
        assert pipeline._cache_enabled is True
        assert pipeline._halt_on_error is False

    def test_init_no_cache(self):
        """Test initialization without cache."""
        pipeline = TransformPipeline(cache_enabled=False)

        assert pipeline._cache is None
        assert pipeline._cache_enabled is False

    def test_init_halt_on_error(self):
        """Test initialization with halt_on_error."""
        pipeline = TransformPipeline(halt_on_error=True)

        assert pipeline._halt_on_error is True

    def test_add_transform(self):
        """Test adding transform."""
        pipeline = TransformPipeline()
        transform = UppercaseTransform()

        pipeline.add_transform(transform)

        assert len(pipeline) == 1
        transforms = pipeline.get_transforms()
        assert len(transforms) == 1
        assert transforms[0] == transform

    def test_add_multiple_transforms(self):
        """Test adding multiple transforms."""
        pipeline = TransformPipeline()

        pipeline.add_transform(UppercaseTransform())
        pipeline.add_transform(LowercaseTransform())
        pipeline.add_transform(ReverseTransform())

        assert len(pipeline) == 3

    def test_remove_transform(self):
        """Test removing transform by name."""
        pipeline = TransformPipeline()

        t1 = UppercaseTransform(name="upper")
        t2 = LowercaseTransform(name="lower")

        pipeline.add_transform(t1)
        pipeline.add_transform(t2)

        assert len(pipeline) == 2

        removed = pipeline.remove_transform("upper")
        assert removed is True
        assert len(pipeline) == 1

        transforms = pipeline.get_transforms()
        assert transforms[0].name == "lower"

    def test_remove_transform_not_found(self):
        """Test removing non-existent transform."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        removed = pipeline.remove_transform("nonexistent")
        assert removed is False
        assert len(pipeline) == 1

    def test_clear_transforms(self):
        """Test clearing all transforms."""
        pipeline = TransformPipeline()

        pipeline.add_transform(UppercaseTransform())
        pipeline.add_transform(LowercaseTransform())

        assert len(pipeline) == 2

        pipeline.clear_transforms()
        assert len(pipeline) == 0

    def test_apply_no_transforms(self):
        """Test applying pipeline with no transforms."""
        pipeline = TransformPipeline()
        content = b"test content"

        result = pipeline.apply(content, "file.txt")

        assert result.success is True
        assert result.content == b"test content"
        assert result.metadata["transforms_applied"] == 0

    def test_apply_single_transform(self):
        """Test applying single transform."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        content = b"hello world"
        result = pipeline.apply(content, "file.txt")

        assert result.success is True
        assert result.content == b"HELLO WORLD"
        assert result.metadata["transforms_applied"] == 1

    def test_apply_chained_transforms(self):
        """Test applying multiple transforms in sequence."""
        pipeline = TransformPipeline()

        # Chain: uppercase -> reverse
        pipeline.add_transform(UppercaseTransform(name="upper"))
        pipeline.add_transform(ReverseTransform(name="reverse"))

        content = b"hello"
        result = pipeline.apply(content, "file.txt")

        assert result.success is True
        # hello -> HELLO -> OLLEH
        assert result.content == b"OLLEH"
        assert result.metadata["transforms_applied"] == 2

    def test_apply_disabled_transform_skipped(self):
        """Test that disabled transforms are skipped."""
        pipeline = TransformPipeline()

        transform = UppercaseTransform(enabled=False)
        pipeline.add_transform(transform)

        content = b"hello"
        result = pipeline.apply(content, "file.txt")

        assert result.success is True
        assert result.content == b"hello"  # Unchanged
        assert result.metadata["transforms_applied"] == 0

    def test_apply_unsupported_path_skipped(self):
        """Test that unsupported paths are skipped."""
        pipeline = TransformPipeline()

        # Only supports .txt files
        pipeline.add_transform(ConditionalTransform())

        content = b"hello"
        result = pipeline.apply(content, "file.py")

        assert result.success is True
        assert result.content == b"hello"  # Unchanged
        assert result.metadata["transforms_applied"] == 0

    def test_apply_with_error_continue(self):
        """Test pipeline continues after error (default behavior)."""
        pipeline = TransformPipeline(halt_on_error=False)

        pipeline.add_transform(UppercaseTransform(name="upper"))
        pipeline.add_transform(FailingTransform(name="failing"))
        pipeline.add_transform(ReverseTransform(name="reverse"))

        content = b"hello"
        result = pipeline.apply(content, "file.txt")

        # Pipeline continues despite error
        assert result.success is False  # At least one failed
        # hello -> HELLO -> [error, content unchanged] -> OLLEH
        assert result.content == b"OLLEH"
        assert result.metadata["transforms_applied"] == 3
        assert result.metadata["pipeline_halted"] is False

    def test_apply_with_error_halt(self):
        """Test pipeline halts on error."""
        pipeline = TransformPipeline(halt_on_error=True)

        pipeline.add_transform(UppercaseTransform(name="upper"))
        pipeline.add_transform(FailingTransform(name="failing"))
        pipeline.add_transform(ReverseTransform(name="reverse"))

        content = b"hello"
        result = pipeline.apply(content, "file.txt")

        # Pipeline halts after error
        assert result.success is False
        # hello -> HELLO -> [error, halted]
        assert result.content == b"HELLO"
        assert result.metadata["transforms_applied"] == 2
        assert result.metadata["pipeline_halted"] is True

    def test_apply_updates_stats(self):
        """Test that apply updates statistics."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        pipeline.apply(b"test1", "file1.txt")
        pipeline.apply(b"test2", "file2.txt")

        stats = pipeline.get_stats()
        assert stats["total_pipelines"] == 2
        assert stats["successful_pipelines"] == 2
        assert stats["failed_pipelines"] == 0

    def test_apply_failed_pipeline_stats(self):
        """Test statistics for failed pipelines."""
        pipeline = TransformPipeline()
        pipeline.add_transform(FailingTransform())

        pipeline.apply(b"test1", "file1.txt")
        pipeline.apply(b"test2", "file2.txt")

        stats = pipeline.get_stats()
        assert stats["total_pipelines"] == 2
        assert stats["successful_pipelines"] == 0
        assert stats["failed_pipelines"] == 2

    def test_caching_enabled(self):
        """Test that caching works."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"
        path = "file.txt"

        # First call - cache miss
        result1 = pipeline.apply(content, path)
        stats1 = pipeline.get_stats()
        assert stats1["cache_misses"] == 1
        assert stats1["cache_hits"] == 0

        # Second call with same content/path - cache hit
        result2 = pipeline.apply(content, path)
        stats2 = pipeline.get_stats()
        assert stats2["cache_misses"] == 1
        assert stats2["cache_hits"] == 1

        # Results should be identical
        assert result1.content == result2.content

    def test_caching_disabled(self):
        """Test that caching can be disabled."""
        pipeline = TransformPipeline(cache_enabled=False)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"
        path = "file.txt"

        # Apply twice
        pipeline.apply(content, path)
        pipeline.apply(content, path)

        stats = pipeline.get_stats()
        # No cache stats when disabled
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0

    def test_skip_cache_option(self):
        """Test skip_cache option."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"
        path = "file.txt"

        # First call with skip_cache
        pipeline.apply(content, path, skip_cache=True)
        stats1 = pipeline.get_stats()
        assert stats1["cache_misses"] == 0
        assert stats1["cache_hits"] == 0

        # Second call without skip_cache - still a miss
        pipeline.apply(content, path, skip_cache=False)
        stats2 = pipeline.get_stats()
        assert stats2["cache_misses"] == 1

    def test_clear_cache(self):
        """Test clearing cache."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"
        path = "file.txt"

        # Apply and cache
        pipeline.apply(content, path)

        # Clear cache
        pipeline.clear_cache()

        # Next apply should be cache miss
        pipeline.apply(content, path)
        stats = pipeline.get_stats()
        assert stats["cache_misses"] == 2  # Both were misses

    def test_enable_transform(self):
        """Test enabling transform by name."""
        pipeline = TransformPipeline()
        transform = UppercaseTransform(name="upper", enabled=False)
        pipeline.add_transform(transform)

        # Initially disabled
        result1 = pipeline.apply(b"hello", "file.txt")
        assert result1.content == b"hello"

        # Enable it
        enabled = pipeline.enable_transform("upper")
        assert enabled is True

        # Now it should work
        result2 = pipeline.apply(b"hello", "file.txt", skip_cache=True)
        assert result2.content == b"HELLO"

    def test_enable_transform_not_found(self):
        """Test enabling non-existent transform."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        enabled = pipeline.enable_transform("nonexistent")
        assert enabled is False

    def test_disable_transform(self):
        """Test disabling transform by name."""
        pipeline = TransformPipeline()
        transform = UppercaseTransform(name="upper", enabled=True)
        pipeline.add_transform(transform)

        # Initially enabled
        result1 = pipeline.apply(b"hello", "file.txt")
        assert result1.content == b"HELLO"

        # Disable it
        disabled = pipeline.disable_transform("upper")
        assert disabled is True

        # Now it should be skipped
        result2 = pipeline.apply(b"hello", "file.txt", skip_cache=True)
        assert result2.content == b"hello"

    def test_disable_transform_not_found(self):
        """Test disabling non-existent transform."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        disabled = pipeline.disable_transform("nonexistent")
        assert disabled is False

    def test_get_stats_with_transform_stats(self):
        """Test that get_stats includes transform-level stats."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform(name="upper"))
        pipeline.add_transform(LowercaseTransform(name="lower"))

        pipeline.apply(b"test", "file.txt")

        stats = pipeline.get_stats()
        assert "transform_stats" in stats
        assert "upper" in stats["transform_stats"]
        assert "lower" in stats["transform_stats"]

    def test_get_stats_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"

        # 1 miss, 2 hits
        pipeline.apply(content, "file.txt")
        pipeline.apply(content, "file.txt")
        pipeline.apply(content, "file.txt")

        stats = pipeline.get_stats()
        assert stats["cache_hits"] == 2
        assert stats["cache_misses"] == 1
        assert stats["cache_hit_rate"] == 2.0 / 3.0

    def test_reset_stats(self):
        """Test resetting all statistics."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        # Apply some transforms
        pipeline.apply(b"test1", "file1.txt")
        pipeline.apply(b"test2", "file2.txt")

        stats1 = pipeline.get_stats()
        assert stats1["total_pipelines"] == 2

        # Reset
        pipeline.reset_stats()

        stats2 = pipeline.get_stats()
        assert stats2["total_pipelines"] == 0
        assert stats2["successful_pipelines"] == 0
        assert stats2["failed_pipelines"] == 0

    def test_repr(self):
        """Test string representation."""
        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform(name="upper"))
        pipeline.add_transform(LowercaseTransform(name="lower"))

        repr_str = repr(pipeline)

        assert "TransformPipeline" in repr_str
        assert "upper" in repr_str
        assert "lower" in repr_str

    def test_metadata_passthrough(self):
        """Test that metadata is passed to transforms."""

        class MetadataTrackingTransform(Transform):
            def __init__(self):
                super().__init__()
                self.received_metadata = None

            def transform(self, content, path, metadata=None):
                self.received_metadata = metadata
                return content

        transform = MetadataTrackingTransform()
        pipeline = TransformPipeline()
        pipeline.add_transform(transform)

        test_metadata = {"key": "value", "number": 42}
        pipeline.apply(b"test", "file.txt", metadata=test_metadata)

        assert transform.received_metadata == test_metadata

    def test_cache_key_different_content(self):
        """Test that different content produces different cache keys."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        # Two different contents
        pipeline.apply(b"hello", "file.txt")
        pipeline.apply(b"world", "file.txt")

        stats = pipeline.get_stats()
        # Both should be cache misses (different content)
        assert stats["cache_misses"] == 2
        assert stats["cache_hits"] == 0

    def test_cache_key_different_path(self):
        """Test that different paths produce different cache keys."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        # Same content, different paths
        content = b"hello"
        pipeline.apply(content, "file1.txt")
        pipeline.apply(content, "file2.txt")

        stats = pipeline.get_stats()
        # Both should be cache misses (different paths)
        assert stats["cache_misses"] == 2
        assert stats["cache_hits"] == 0

    def test_cache_key_different_transforms(self):
        """Test that changing transforms invalidates cache."""
        pipeline = TransformPipeline(cache_enabled=True)
        pipeline.add_transform(UppercaseTransform())

        content = b"hello"
        path = "file.txt"

        # First apply
        pipeline.apply(content, path)

        # Add another transform
        pipeline.add_transform(LowercaseTransform())

        # Second apply - should be cache miss (transform config changed)
        pipeline.apply(content, path)

        stats = pipeline.get_stats()
        assert stats["cache_misses"] == 2

    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading

        pipeline = TransformPipeline()
        pipeline.add_transform(UppercaseTransform())

        results = []

        def apply_transform():
            result = pipeline.apply(b"test", "file.txt", skip_cache=True)
            results.append(result)

        # Run multiple threads
        threads = [threading.Thread(target=apply_transform) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 10
        assert all(r.success for r in results)
