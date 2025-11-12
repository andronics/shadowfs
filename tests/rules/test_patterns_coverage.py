"""Tests to fill coverage gaps in patterns module.

This module tests edge cases to achieve 100% coverage.
"""
import pytest

from shadowfs.rules.patterns import PatternEntry, PatternMatcher, PatternType


class TestPatternMatcherCoverageGaps:
    """Tests for PatternMatcher coverage gaps."""

    def test_matches_with_unknown_pattern_type(self):
        """Test _matches_entry() with unknown pattern type returns False (line 196)."""
        matcher = PatternMatcher()

        # Create a pattern entry with an invalid pattern type
        entry = PatternEntry(pattern="*.py", pattern_type=PatternType.GLOB)

        # Manually override to invalid type to test fallback
        entry.pattern_type = "INVALID_TYPE"  # type: ignore

        # Should return False for unknown pattern type
        result = matcher._matches_entry("/test/file.py", entry)
        assert result is False
