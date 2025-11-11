#!/usr/bin/env python3
"""Comprehensive tests for Transform base classes."""

import time

import pytest

from shadowfs.transforms.base import (
    Transform,
    TransformError,
    TransformResult,
    TransformType,
)


class TestTransformType:
    """Tests for TransformType enum."""

    def test_template(self):
        """Test TEMPLATE type."""
        assert TransformType.TEMPLATE.value == "template"

    def test_compression(self):
        """Test COMPRESSION type."""
        assert TransformType.COMPRESSION.value == "compression"

    def test_encryption(self):
        """Test ENCRYPTION type."""
        assert TransformType.ENCRYPTION.value == "encryption"

    def test_conversion(self):
        """Test CONVERSION type."""
        assert TransformType.CONVERSION.value == "conversion"

    def test_custom(self):
        """Test CUSTOM type."""
        assert TransformType.CUSTOM.value == "custom"


class TestTransformResult:
    """Tests for TransformResult dataclass."""

    def test_creation_minimal(self):
        """Test creating minimal TransformResult."""
        result = TransformResult(content=b"test")

        assert result.content == b"test"
        assert result.success is True
        assert result.error is None
        assert result.metadata == {}
        assert result.transform_name is None
        assert result.duration_ms == 0.0

    def test_creation_full(self):
        """Test creating full TransformResult."""
        metadata = {"key": "value"}
        result = TransformResult(
            content=b"transformed",
            success=False,
            error="Test error",
            metadata=metadata,
            transform_name="test_transform",
            duration_ms=123.45,
        )

        assert result.content == b"transformed"
        assert result.success is False
        assert result.error == "Test error"
        assert result.metadata == metadata
        assert result.transform_name == "test_transform"
        assert result.duration_ms == 123.45


class TestTransformError:
    """Tests for TransformError exception."""

    def test_creation_minimal(self):
        """Test creating minimal TransformError."""
        error = TransformError("Test error")

        assert error.message == "Test error"
        assert error.transform_name is None
        assert str(error) == "Test error"

    def test_creation_with_name(self):
        """Test creating TransformError with transform name."""
        error = TransformError("Test error", transform_name="my_transform")

        assert error.message == "Test error"
        assert error.transform_name == "my_transform"


class SimpleTransform(Transform):
    """Simple transform for testing."""

    def transform(self, content, path, metadata=None):
        """Return content uppercased."""
        return content.upper()


class FailingTransform(Transform):
    """Transform that always fails."""

    def transform(self, content, path, metadata=None):
        """Raise error."""
        raise TransformError("Intentional failure", self.name)


class ConditionalTransform(Transform):
    """Transform that only supports .txt files."""

    def supports(self, path, metadata=None):
        """Only support .txt files."""
        return path.endswith(".txt")

    def transform(self, content, path, metadata=None):
        """Return content uppercased."""
        return content.upper()


class HookTransform(Transform):
    """Transform with hooks for testing."""

    def __init__(self):
        super().__init__(name="hook_transform")
        self.before_called = False
        self.after_called = False

    def before_transform(self, content, path, metadata):
        """Track before hook call."""
        self.before_called = True

    def transform(self, content, path, metadata=None):
        """Return content uppercased."""
        return content.upper()

    def after_transform(self, content, path, metadata):
        """Track after hook call and modify content."""
        self.after_called = True
        return content + b" [MODIFIED]"


class TestTransform:
    """Tests for Transform base class."""

    def test_init_default(self):
        """Test default initialization."""
        transform = SimpleTransform()

        assert transform.name == "SimpleTransform"
        assert transform.enabled is True
        assert transform._stats["total_transforms"] == 0

    def test_init_custom_name(self):
        """Test initialization with custom name."""
        transform = SimpleTransform(name="custom_name")

        assert transform.name == "custom_name"

    def test_init_disabled(self):
        """Test initialization with disabled flag."""
        transform = SimpleTransform(enabled=False)

        assert transform.enabled is False

    def test_supports_default(self):
        """Test default supports returns True."""
        transform = SimpleTransform()

        assert transform.supports("any_file.py") is True
        assert transform.supports("any_file.txt") is True

    def test_supports_conditional(self):
        """Test conditional supports."""
        transform = ConditionalTransform()

        assert transform.supports("file.txt") is True
        assert transform.supports("file.py") is False

    def test_apply_success(self):
        """Test successful transform application."""
        transform = SimpleTransform()
        content = b"hello world"

        result = transform.apply(content, "test.txt")

        assert result.success is True
        assert result.content == b"HELLO WORLD"
        assert result.error is None
        assert result.transform_name == "SimpleTransform"
        assert result.duration_ms > 0

    def test_apply_updates_stats(self):
        """Test that apply updates statistics."""
        transform = SimpleTransform()

        result1 = transform.apply(b"test1", "file1.txt")
        result2 = transform.apply(b"test2", "file2.txt")

        stats = transform.get_stats()
        assert stats["total_transforms"] == 2
        assert stats["successful_transforms"] == 2
        assert stats["failed_transforms"] == 0
        assert stats["avg_duration_ms"] > 0
        assert stats["success_rate"] == 1.0

    def test_apply_disabled_transform(self):
        """Test applying disabled transform skips transformation."""
        transform = SimpleTransform(enabled=False)
        content = b"hello world"

        result = transform.apply(content, "test.txt")

        assert result.success is True
        assert result.content == b"hello world"  # Unchanged
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "Transform disabled"

    def test_apply_unsupported_path(self):
        """Test applying transform to unsupported path."""
        transform = ConditionalTransform()
        content = b"hello world"

        result = transform.apply(content, "test.py")

        assert result.success is True
        assert result.content == b"hello world"  # Unchanged
        assert result.metadata["skipped"] is True
        assert result.metadata["reason"] == "Path not supported"

    def test_apply_with_error(self):
        """Test transform that raises error."""
        transform = FailingTransform()
        content = b"test"

        result = transform.apply(content, "test.txt")

        assert result.success is False
        assert result.content == b"test"  # Original returned on error
        assert result.error is not None
        assert "Intentional failure" in result.error

    def test_apply_error_updates_stats(self):
        """Test that errors update statistics."""
        transform = FailingTransform()

        result1 = transform.apply(b"test1", "file1.txt")
        result2 = transform.apply(b"test2", "file2.txt")

        stats = transform.get_stats()
        assert stats["total_transforms"] == 2
        assert stats["successful_transforms"] == 0
        assert stats["failed_transforms"] == 2
        assert stats["success_rate"] == 0.0

    def test_before_transform_hook(self):
        """Test before_transform hook is called."""
        transform = HookTransform()

        result = transform.apply(b"test", "file.txt")

        assert transform.before_called is True

    def test_after_transform_hook(self):
        """Test after_transform hook is called and can modify content."""
        transform = HookTransform()

        result = transform.apply(b"test", "file.txt")

        assert transform.after_called is True
        assert result.content == b"TEST [MODIFIED]"

    def test_get_metadata_default(self):
        """Test default get_metadata."""
        transform = SimpleTransform()

        metadata = transform.get_metadata("test.txt")

        assert metadata == {"transform": "SimpleTransform"}

    def test_get_stats_empty(self):
        """Test get_stats with no transforms."""
        transform = SimpleTransform()

        stats = transform.get_stats()

        assert stats["total_transforms"] == 0
        assert stats["successful_transforms"] == 0
        assert stats["failed_transforms"] == 0
        assert stats["avg_duration_ms"] == 0.0
        assert stats["success_rate"] == 0.0

    def test_reset_stats(self):
        """Test resetting statistics."""
        transform = SimpleTransform()

        # Apply some transforms
        transform.apply(b"test1", "file1.txt")
        transform.apply(b"test2", "file2.txt")

        assert transform.get_stats()["total_transforms"] == 2

        # Reset
        transform.reset_stats()

        stats = transform.get_stats()
        assert stats["total_transforms"] == 0
        assert stats["successful_transforms"] == 0
        assert stats["failed_transforms"] == 0

    def test_enable(self):
        """Test enabling transform."""
        transform = SimpleTransform(enabled=False)
        assert transform.enabled is False

        transform.enable()
        assert transform.enabled is True

    def test_disable(self):
        """Test disabling transform."""
        transform = SimpleTransform(enabled=True)
        assert transform.enabled is True

        transform.disable()
        assert transform.enabled is False

    def test_repr(self):
        """Test string representation."""
        transform = SimpleTransform(name="test_transform")

        repr_str = repr(transform)

        assert "SimpleTransform" in repr_str
        assert "test_transform" in repr_str
        assert "enabled" in repr_str

    def test_repr_disabled(self):
        """Test string representation when disabled."""
        transform = SimpleTransform(enabled=False)

        repr_str = repr(transform)

        assert "disabled" in repr_str

    def test_timing_accuracy(self):
        """Test that duration timing is accurate."""

        class SlowTransform(Transform):
            def transform(self, content, path, metadata=None):
                time.sleep(0.01)  # Sleep 10ms
                return content

        transform = SlowTransform()
        result = transform.apply(b"test", "file.txt")

        # Should have taken at least 10ms
        assert result.duration_ms >= 10.0

    def test_multiple_transforms_stats(self):
        """Test statistics with mix of success and failure."""

        class SometimesFailTransform(Transform):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def transform(self, content, path, metadata=None):
                self.call_count += 1
                if self.call_count % 2 == 0:
                    raise TransformError("Even number fail")
                return content.upper()

        transform = SometimesFailTransform()

        # Apply 4 times
        transform.apply(b"test1", "file1.txt")  # Success
        transform.apply(b"test2", "file2.txt")  # Fail
        transform.apply(b"test3", "file3.txt")  # Success
        transform.apply(b"test4", "file4.txt")  # Fail

        stats = transform.get_stats()
        assert stats["total_transforms"] == 4
        assert stats["successful_transforms"] == 2
        assert stats["failed_transforms"] == 2
        assert stats["success_rate"] == 0.5

    def test_metadata_passthrough(self):
        """Test that metadata is passed to transform method."""

        class MetadataTrackingTransform(Transform):
            def __init__(self):
                super().__init__()
                self.received_metadata = None

            def transform(self, content, path, metadata=None):
                self.received_metadata = metadata
                return content

        transform = MetadataTrackingTransform()
        test_metadata = {"key": "value", "number": 42}

        transform.apply(b"test", "file.txt", metadata=test_metadata)

        assert transform.received_metadata == test_metadata

    def test_exception_not_transform_error(self):
        """Test handling of non-TransformError exceptions."""

        class GenericErrorTransform(Transform):
            def transform(self, content, path, metadata=None):
                raise ValueError("Generic error")

        transform = GenericErrorTransform()
        result = transform.apply(b"test", "file.txt")

        assert result.success is False
        assert "Generic error" in result.error
        assert result.content == b"test"  # Original content returned
