"""Tests to fill coverage gaps in transforms modules.

This module tests edge cases to achieve 100% coverage.
"""
import pytest

from shadowfs.transforms.pipeline import TransformPipeline


class TestTransformPipelineCoverageGaps:
    """Tests for TransformPipeline coverage gaps."""

    def test_clear_cache_without_cache_manager(self):
        """Test clear_cache() when no cache manager is configured (line 279->exit)."""
        # Create pipeline with cache disabled
        pipeline = TransformPipeline(cache_enabled=False)

        # clear_cache() should handle None cache gracefully
        pipeline.clear_cache()  # Should not raise exception

        # Verify it completed without error
        assert pipeline._cache is None
