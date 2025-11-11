#!/usr/bin/env python3
"""Comprehensive tests for PatternMatcher."""

import re

import pytest

from shadowfs.integration.pattern_matcher import (
    MultiMatcher,
    PatternEntry,
    PatternMatcher,
    PatternType,
)


class TestPatternMatcher:
    """Tests for PatternMatcher class."""

    def test_init_default(self):
        """Test default initialization."""
        matcher = PatternMatcher()
        assert len(matcher) == 0
        assert not matcher
        assert matcher._case_sensitive is True

    def test_init_case_insensitive(self):
        """Test case-insensitive initialization."""
        matcher = PatternMatcher(case_sensitive=False)
        assert matcher._case_sensitive is False

    def test_add_glob_pattern(self):
        """Test adding glob pattern."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py")

        assert len(matcher) == 1
        assert bool(matcher)

        patterns = matcher.get_patterns()
        assert len(patterns) == 1
        assert patterns[0].pattern == "*.py"
        assert patterns[0].pattern_type == PatternType.GLOB

    def test_add_glob_pattern_with_name(self):
        """Test adding named glob pattern."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py", name="python_files")

        patterns = matcher.get_patterns()
        assert patterns[0].name == "python_files"

    def test_add_regex_pattern(self):
        """Test adding regex pattern."""
        matcher = PatternMatcher()
        matcher.add_regex_pattern(r"test_.*\.py$")

        assert len(matcher) == 1
        patterns = matcher.get_patterns()
        assert patterns[0].pattern == r"test_.*\.py$"
        assert patterns[0].pattern_type == PatternType.REGEX
        assert isinstance(patterns[0].compiled, re.Pattern)

    def test_add_regex_pattern_case_insensitive(self):
        """Test adding case-insensitive regex pattern."""
        matcher = PatternMatcher()
        matcher.add_regex_pattern(r"TEST.*", case_sensitive=False)

        patterns = matcher.get_patterns()
        assert patterns[0].case_sensitive is False
        # Check that IGNORECASE flag is set
        assert patterns[0].compiled.flags & re.IGNORECASE

    def test_matches_simple_glob(self):
        """Test simple glob matching."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py")

        assert matcher.matches("test.py")
        assert matcher.matches("/path/to/test.py")
        assert not matcher.matches("test.txt")
        assert not matcher.matches("test.pyc")

    def test_matches_recursive_glob(self):
        """Test recursive glob pattern with **."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("**/*.py")

        assert matcher.matches("test.py")
        assert matcher.matches("src/test.py")
        assert matcher.matches("src/subdir/test.py")
        assert matcher.matches("a/b/c/d/test.py")
        assert not matcher.matches("test.txt")

    def test_matches_glob_with_path(self):
        """Test glob matching with path segments."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("src/**/*.py")

        assert matcher.matches("src/test.py")
        assert matcher.matches("src/subdir/test.py")
        assert not matcher.matches("test.py")
        assert not matcher.matches("tests/test.py")

    def test_matches_regex(self):
        """Test regex pattern matching."""
        matcher = PatternMatcher()
        matcher.add_regex_pattern(r"^test_.*\.py$")

        assert matcher.matches("test_something.py")
        assert matcher.matches("test_foo.py")
        assert not matcher.matches("something_test.py")
        assert not matcher.matches("test_foo.txt")

    def test_matches_multiple_patterns(self):
        """Test matching with multiple patterns (OR logic)."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py")
        matcher.add_glob_pattern("*.txt")

        assert matcher.matches("test.py")
        assert matcher.matches("test.txt")
        assert not matcher.matches("test.md")

    def test_matches_case_insensitive(self):
        """Test case-insensitive matching."""
        matcher = PatternMatcher(case_sensitive=False)
        matcher.add_glob_pattern("*.PY")

        assert matcher.matches("test.py")
        assert matcher.matches("test.PY")
        assert matcher.matches("test.Py")

    def test_matches_no_patterns(self):
        """Test matching with no patterns returns False."""
        matcher = PatternMatcher()
        assert not matcher.matches("anything.py")

    def test_get_matching_patterns(self):
        """Test getting all matching pattern names."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py", name="python")
        matcher.add_glob_pattern("test_*.py", name="tests")
        matcher.add_regex_pattern(r".*_test\.py$", name="test_suffix")

        matches = matcher.get_matching_patterns("test_foo.py")
        assert "python" in matches
        assert "tests" in matches
        assert "test_suffix" not in matches

        matches = matcher.get_matching_patterns("foo_test.py")
        assert "python" in matches
        assert "tests" not in matches
        assert "test_suffix" in matches

    def test_clear(self):
        """Test clearing all patterns."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py")
        matcher.add_regex_pattern(r"test.*")

        assert len(matcher) == 2

        matcher.clear()
        assert len(matcher) == 0
        assert not matcher

    def test_remove_pattern(self):
        """Test removing pattern by name."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py", name="python")
        matcher.add_glob_pattern("*.txt", name="text")

        assert len(matcher) == 2

        removed = matcher.remove_pattern("python")
        assert removed is True
        assert len(matcher) == 1

        patterns = matcher.get_patterns()
        assert patterns[0].name == "text"

    def test_remove_pattern_not_found(self):
        """Test removing non-existent pattern."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py", name="python")

        removed = matcher.remove_pattern("nonexistent")
        assert removed is False
        assert len(matcher) == 1

    def test_normalize_path(self):
        """Test path normalization."""
        matcher = PatternMatcher()

        # Windows-style path
        assert matcher._normalize_path("C:\\path\\to\\file.py", True) == "C:/path/to/file.py"

        # Leading slash removal
        assert matcher._normalize_path("/path/to/file.py", True) == "path/to/file.py"

        # Case insensitive
        assert (
            matcher._normalize_path("Path/To/File.PY", False) == "path/to/file.py"
        )

    def test_matches_with_backslashes(self):
        """Test matching with Windows-style backslashes."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("src/**/*.py")

        # Should match with backslashes (normalized internally)
        assert matcher.matches("src\\subdir\\test.py")

    def test_double_asterisk_beginning(self):
        """Test ** at beginning of pattern."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("**/*.py")

        assert matcher.matches("test.py")
        assert matcher.matches("a/test.py")
        assert matcher.matches("a/b/c/test.py")

    def test_double_asterisk_middle(self):
        """Test ** in middle of pattern."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("src/**/test.py")

        assert matcher.matches("src/test.py")
        assert matcher.matches("src/subdir/test.py")
        assert matcher.matches("src/a/b/c/test.py")
        assert not matcher.matches("test.py")
        assert not matcher.matches("tests/test.py")

    def test_question_mark_glob(self):
        """Test ? wildcard in glob patterns."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("test?.py")

        assert matcher.matches("test1.py")
        assert matcher.matches("testa.py")
        assert not matcher.matches("test.py")
        assert not matcher.matches("test12.py")

    def test_glob_character_class(self):
        """Test character classes in glob patterns."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("test[0-9].py")

        assert matcher.matches("test0.py")
        assert matcher.matches("test5.py")
        assert matcher.matches("test9.py")
        assert not matcher.matches("testa.py")
        assert not matcher.matches("test.py")

    def test_multiple_extensions(self):
        """Test matching multiple file extensions."""
        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.{py,txt,md}")

        # Note: fnmatch doesn't support brace expansion
        # This test documents current behavior
        assert not matcher.matches("test.py")
        assert not matcher.matches("test.txt")

        # Alternative approach: multiple patterns
        matcher2 = PatternMatcher()
        matcher2.add_glob_pattern("*.py")
        matcher2.add_glob_pattern("*.txt")
        matcher2.add_glob_pattern("*.md")

        assert matcher2.matches("test.py")
        assert matcher2.matches("test.txt")
        assert matcher2.matches("test.md")

    def test_len_operator(self):
        """Test __len__ operator."""
        matcher = PatternMatcher()
        assert len(matcher) == 0

        matcher.add_glob_pattern("*.py")
        assert len(matcher) == 1

        matcher.add_regex_pattern(r"test.*")
        assert len(matcher) == 2

    def test_bool_operator(self):
        """Test __bool__ operator."""
        matcher = PatternMatcher()
        assert not bool(matcher)

        matcher.add_glob_pattern("*.py")
        assert bool(matcher)


class TestMultiMatcher:
    """Tests for MultiMatcher class."""

    def test_init(self):
        """Test initialization."""
        matcher = MultiMatcher()
        assert matcher._include is not None
        assert matcher._exclude is not None

    def test_add_include_glob(self):
        """Test adding include glob pattern."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB)

        assert len(matcher._include) == 1

    def test_add_include_regex(self):
        """Test adding include regex pattern."""
        matcher = MultiMatcher()
        matcher.add_include_pattern(r"test.*\.py$", PatternType.REGEX)

        assert len(matcher._include) == 1

    def test_add_exclude_glob(self):
        """Test adding exclude glob pattern."""
        matcher = MultiMatcher()
        matcher.add_exclude_pattern("*.pyc", PatternType.GLOB)

        assert len(matcher._exclude) == 1

    def test_matches_no_patterns_default_allow(self):
        """Test matching with no patterns defaults to allow."""
        matcher = MultiMatcher()
        assert matcher.matches("anything.py") is True

    def test_matches_exclude_only(self):
        """Test matching with exclude patterns only."""
        matcher = MultiMatcher()
        matcher.add_exclude_pattern("*.pyc", PatternType.GLOB)
        matcher.add_exclude_pattern("__pycache__/**", PatternType.GLOB)

        assert matcher.matches("test.py") is True
        assert matcher.matches("test.pyc") is False
        assert matcher.matches("__pycache__/test.py") is False

    def test_matches_include_only(self):
        """Test matching with include patterns only."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB)
        matcher.add_include_pattern("*.txt", PatternType.GLOB)

        assert matcher.matches("test.py") is True
        assert matcher.matches("test.txt") is True
        assert matcher.matches("test.md") is False

    def test_matches_include_and_exclude(self):
        """Test matching with both include and exclude patterns."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB)
        matcher.add_exclude_pattern("test_*.py", PatternType.GLOB)

        assert matcher.matches("main.py") is True
        assert matcher.matches("utils.py") is True
        assert matcher.matches("test_main.py") is False
        assert matcher.matches("test_utils.py") is False
        assert matcher.matches("main.txt") is False

    def test_matches_exclude_precedence(self):
        """Test that exclude patterns take precedence."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("**/*.py", PatternType.GLOB)
        matcher.add_exclude_pattern("**/test_*.py", PatternType.GLOB)

        assert matcher.matches("src/main.py") is True
        assert matcher.matches("src/test_main.py") is False

    def test_get_matchers(self):
        """Test getting include/exclude matchers."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB)
        matcher.add_exclude_pattern("*.pyc", PatternType.GLOB)

        include = matcher.get_include_matcher()
        exclude = matcher.get_exclude_matcher()

        assert len(include) == 1
        assert len(exclude) == 1
        assert include.matches("test.py")
        assert exclude.matches("test.pyc")

    def test_clear(self):
        """Test clearing all patterns."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB)
        matcher.add_exclude_pattern("*.pyc", PatternType.GLOB)

        assert len(matcher._include) == 1
        assert len(matcher._exclude) == 1

        matcher.clear()

        assert len(matcher._include) == 0
        assert len(matcher._exclude) == 0

    def test_complex_scenario(self):
        """Test complex real-world scenario."""
        matcher = MultiMatcher()

        # Include all Python files
        matcher.add_include_pattern("**/*.py", PatternType.GLOB)

        # Exclude test files
        matcher.add_exclude_pattern("**/test_*.py", PatternType.GLOB)
        matcher.add_exclude_pattern("**/tests/**", PatternType.GLOB)

        # Exclude build artifacts
        matcher.add_exclude_pattern("**/__pycache__/**", PatternType.GLOB)
        matcher.add_exclude_pattern("**/*.pyc", PatternType.GLOB)

        # Should match
        assert matcher.matches("src/main.py") is True
        assert matcher.matches("lib/utils.py") is True

        # Should exclude
        assert matcher.matches("src/test_main.py") is False
        assert matcher.matches("tests/test_utils.py") is False
        assert matcher.matches("__pycache__/main.cpython-311.pyc") is False
        assert matcher.matches("src/main.pyc") is False

    def test_case_sensitive_propagation(self):
        """Test that case sensitivity propagates to sub-matchers."""
        matcher = MultiMatcher(case_sensitive=False)
        matcher.add_include_pattern("*.PY", PatternType.GLOB)

        assert matcher.matches("test.py") is True
        assert matcher.matches("test.PY") is True

    def test_named_patterns(self):
        """Test using named patterns in MultiMatcher."""
        matcher = MultiMatcher()
        matcher.add_include_pattern("*.py", PatternType.GLOB, name="python")
        matcher.add_exclude_pattern("*_test.py", PatternType.GLOB, name="tests")

        include = matcher.get_include_matcher()
        exclude = matcher.get_exclude_matcher()

        inc_patterns = include.get_patterns()
        exc_patterns = exclude.get_patterns()

        assert inc_patterns[0].name == "python"
        assert exc_patterns[0].name == "tests"


class TestPatternEntry:
    """Tests for PatternEntry dataclass."""

    def test_creation(self):
        """Test creating PatternEntry."""
        entry = PatternEntry(
            pattern="*.py", pattern_type=PatternType.GLOB, case_sensitive=True
        )

        assert entry.pattern == "*.py"
        assert entry.pattern_type == PatternType.GLOB
        assert entry.case_sensitive is True
        assert entry.compiled is None
        assert entry.name is None

    def test_with_compiled(self):
        """Test PatternEntry with compiled pattern."""
        compiled = re.compile(r"test.*")
        entry = PatternEntry(
            pattern=r"test.*",
            pattern_type=PatternType.REGEX,
            compiled=compiled,
        )

        assert entry.compiled is compiled

    def test_with_name(self):
        """Test PatternEntry with name."""
        entry = PatternEntry(
            pattern="*.py", pattern_type=PatternType.GLOB, name="python_files"
        )

        assert entry.name == "python_files"


class TestEdgeCases:
    """Test edge cases and coverage completion."""

    def test_path_object_input(self):
        """Test matching with Path object input."""
        from pathlib import Path

        matcher = PatternMatcher()
        matcher.add_glob_pattern("*.py")

        # Pass Path object instead of string
        path_obj = Path("test.py")
        assert matcher.matches(path_obj) is True

    def test_add_exclude_regex_pattern(self):
        """Test adding exclude regex pattern to MultiMatcher."""
        matcher = MultiMatcher()
        matcher.add_exclude_pattern(r"test_.*\.py$", PatternType.REGEX)

        assert len(matcher._exclude) == 1
        assert matcher.matches("test_foo.py") is False
        assert matcher.matches("main.py") is True

    def test_regex_pattern_with_none_compiled(self):
        """Test regex matching with None compiled pattern (defensive)."""
        matcher = PatternMatcher()

        # Create entry with None compiled (shouldn't happen in normal use)
        entry = PatternEntry(
            pattern=r"test.*",
            pattern_type=PatternType.REGEX,
            compiled=None,
            case_sensitive=True,
        )
        matcher._patterns.append(entry)

        # Should not match anything since compiled is None
        assert matcher.matches("test.py") is False
