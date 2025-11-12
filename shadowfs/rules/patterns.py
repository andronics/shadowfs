#!/usr/bin/env python3
r"""Pattern matching for file paths with glob and regex support.

This module provides pattern matching functionality for ShadowFS:
- Glob pattern matching (*.py, **/*.txt)
- Regex pattern matching with compiled patterns
- Path normalization for consistent matching
- Case-sensitive and case-insensitive modes
- Multiple pattern support with OR logic

Example:
    >>> matcher = PatternMatcher()
    >>> matcher.add_glob_pattern("**/*.py")
    >>> matcher.add_regex_pattern(r"test_.*\.py$")
    >>> matcher.matches("/path/to/test_file.py")
    True
"""

import fnmatch
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Pattern, Set, Union


class PatternType(Enum):
    """Pattern matching type."""

    GLOB = "glob"  # Shell-style patterns (*.txt, **/*.py)
    REGEX = "regex"  # Regular expressions


@dataclass
class PatternEntry:
    """A single pattern entry with metadata."""

    pattern: str
    pattern_type: PatternType
    compiled: Optional[Union[Pattern, str]] = None
    case_sensitive: bool = True
    name: Optional[str] = None


class PatternMatcher:
    """Pattern matcher supporting glob and regex patterns.

    Features:
    - Multiple pattern types (glob, regex)
    - Case-sensitive/insensitive matching
    - Path normalization
    - Compiled pattern caching
    - OR logic (matches any pattern)
    """

    def __init__(self, case_sensitive: bool = True):
        """Initialize pattern matcher.

        Args:
            case_sensitive: Whether patterns are case-sensitive
        """
        self._patterns: List[PatternEntry] = []
        self._case_sensitive = case_sensitive

    def add_glob_pattern(
        self, pattern: str, name: Optional[str] = None, case_sensitive: Optional[bool] = None
    ) -> None:
        """Add glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.py", "**/*.txt")
            name: Optional name for this pattern
            case_sensitive: Override default case sensitivity
        """
        is_case_sensitive = case_sensitive if case_sensitive is not None else self._case_sensitive

        # Normalize pattern
        normalized = self._normalize_pattern(pattern, is_case_sensitive)

        entry = PatternEntry(
            pattern=pattern,
            pattern_type=PatternType.GLOB,
            compiled=normalized,
            case_sensitive=is_case_sensitive,
            name=name,
        )
        self._patterns.append(entry)

    def add_regex_pattern(
        self, pattern: str, name: Optional[str] = None, case_sensitive: Optional[bool] = None
    ) -> None:
        """Add regex pattern.

        Args:
            pattern: Regular expression pattern
            name: Optional name for this pattern
            case_sensitive: Override default case sensitivity
        """
        is_case_sensitive = case_sensitive if case_sensitive is not None else self._case_sensitive

        # Compile regex
        flags = 0 if is_case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)

        entry = PatternEntry(
            pattern=pattern,
            pattern_type=PatternType.REGEX,
            compiled=compiled,
            case_sensitive=is_case_sensitive,
            name=name,
        )
        self._patterns.append(entry)

    def _normalize_pattern(self, pattern: str, case_sensitive: bool) -> str:
        """Normalize glob pattern.

        Args:
            pattern: Raw glob pattern
            case_sensitive: Whether to preserve case

        Returns:
            Normalized pattern
        """
        # Convert to lowercase if case-insensitive
        if not case_sensitive:
            pattern = pattern.lower()

        # Normalize path separators
        pattern = pattern.replace("\\", "/")

        return pattern

    def _normalize_path(self, path: str, case_sensitive: bool) -> str:
        """Normalize file path for matching.

        Args:
            path: File path to normalize
            case_sensitive: Whether to preserve case

        Returns:
            Normalized path
        """
        # Convert to string if Path object
        if isinstance(path, Path):
            path = str(path)

        # Normalize separators
        path = path.replace("\\", "/")

        # Remove leading slash for consistent matching
        path = path.lstrip("/")

        # Convert to lowercase if case-insensitive
        if not case_sensitive:
            path = path.lower()

        return path

    def matches(self, path: str) -> bool:
        """Check if path matches any pattern.

        Args:
            path: File path to check

        Returns:
            True if path matches any pattern
        """
        if not self._patterns:
            return False

        for entry in self._patterns:
            if self._matches_entry(path, entry):
                return True

        return False

    def _matches_entry(self, path: str, entry: PatternEntry) -> bool:
        """Check if path matches a specific pattern entry.

        Args:
            path: File path to check
            entry: Pattern entry to match against

        Returns:
            True if path matches this entry
        """
        # Normalize path
        normalized_path = self._normalize_path(path, entry.case_sensitive)

        if entry.pattern_type == PatternType.GLOB:
            return self._matches_glob(normalized_path, entry)
        elif entry.pattern_type == PatternType.REGEX:
            return self._matches_regex(normalized_path, entry)

        return False

    def _matches_glob(self, path: str, entry: PatternEntry) -> bool:
        """Match path against glob pattern.

        Args:
            path: Normalized path
            entry: Pattern entry with glob pattern

        Returns:
            True if matches
        """
        pattern = entry.compiled

        # Handle ** recursive wildcard
        if "**" in pattern:
            # Convert ** to match any number of path segments (including zero)
            # Example: **/*.py should match:
            # - test.py (zero segments)
            # - src/test.py (one segment)
            # - src/sub/test.py (two segments)

            # Use a placeholder for ** first to avoid conflicts
            DOUBLESTAR_PLACEHOLDER = "\x00DOUBLESTAR\x00"
            STAR_PLACEHOLDER = "\x00STAR\x00"
            QUESTION_PLACEHOLDER = "\x00QUESTION\x00"

            # Replace patterns with placeholders
            regex_pattern = pattern
            regex_pattern = regex_pattern.replace("**", DOUBLESTAR_PLACEHOLDER)
            regex_pattern = regex_pattern.replace("*", STAR_PLACEHOLDER)
            regex_pattern = regex_pattern.replace("?", QUESTION_PLACEHOLDER)

            # Escape regex special chars (now pattern wildcards are safe)
            regex_pattern = re.escape(regex_pattern)

            # Now replace placeholders with proper regex
            # ** preceded by / or at start → (.*/)? (optional path prefix)
            regex_pattern = regex_pattern.replace(
                re.escape(DOUBLESTAR_PLACEHOLDER) + re.escape("/"),
                "(?:.*/|)",  # Matches path/ or nothing
            )
            # ** after / or at end → (/.*)?  (optional path suffix)
            regex_pattern = regex_pattern.replace(
                re.escape("/") + re.escape(DOUBLESTAR_PLACEHOLDER),
                "(?:/.*|)",  # Matches /path or nothing
            )
            # Bare ** → .* (matches anything)
            regex_pattern = regex_pattern.replace(re.escape(DOUBLESTAR_PLACEHOLDER), ".*")

            # * matches any characters except /
            regex_pattern = regex_pattern.replace(re.escape(STAR_PLACEHOLDER), "[^/]*")
            # ? matches single character except /
            regex_pattern = regex_pattern.replace(re.escape(QUESTION_PLACEHOLDER), "[^/]")

            regex_pattern = "^" + regex_pattern + "$"
            return bool(re.match(regex_pattern, path))
        else:
            # Simple glob pattern, use fnmatch
            return fnmatch.fnmatch(path, pattern)

    def _matches_regex(self, path: str, entry: PatternEntry) -> bool:
        """Match path against regex pattern.

        Args:
            path: Normalized path
            entry: Pattern entry with compiled regex

        Returns:
            True if matches
        """
        if entry.compiled is None:
            return False

        return bool(entry.compiled.search(path))

    def get_matching_patterns(self, path: str) -> List[str]:
        """Get all pattern names that match the path.

        Args:
            path: File path to check

        Returns:
            List of matching pattern names
        """
        matches = []
        for entry in self._patterns:
            if self._matches_entry(path, entry):
                matches.append(entry.name or entry.pattern)
        return matches

    def clear(self) -> None:
        """Clear all patterns."""
        self._patterns.clear()

    def remove_pattern(self, name: str) -> bool:
        """Remove pattern by name.

        Args:
            name: Pattern name to remove

        Returns:
            True if pattern was found and removed
        """
        for i, entry in enumerate(self._patterns):
            if entry.name == name:
                self._patterns.pop(i)
                return True
        return False

    def get_patterns(self) -> List[PatternEntry]:
        """Get all registered patterns.

        Returns:
            List of pattern entries
        """
        return self._patterns.copy()

    def __len__(self) -> int:
        """Return number of patterns."""
        return len(self._patterns)

    def __bool__(self) -> bool:
        """Return True if any patterns are registered."""
        return bool(self._patterns)


class MultiMatcher:
    """Multiple pattern matchers with include/exclude logic.

    Implements first-match-wins precedence:
    1. Check exclude patterns first
    2. If excluded, return False
    3. Check include patterns
    4. If no include patterns, return True (default allow)
    5. If include patterns exist, must match at least one
    """

    def __init__(self, case_sensitive: bool = True):
        """Initialize multi-matcher.

        Args:
            case_sensitive: Default case sensitivity
        """
        self._include = PatternMatcher(case_sensitive)
        self._exclude = PatternMatcher(case_sensitive)

    def add_include_pattern(
        self, pattern: str, pattern_type: PatternType = PatternType.GLOB, name: Optional[str] = None
    ) -> None:
        """Add include pattern.

        Args:
            pattern: Pattern string
            pattern_type: Type of pattern (glob or regex)
            name: Optional pattern name
        """
        if pattern_type == PatternType.GLOB:
            self._include.add_glob_pattern(pattern, name)
        else:
            self._include.add_regex_pattern(pattern, name)

    def add_exclude_pattern(
        self, pattern: str, pattern_type: PatternType = PatternType.GLOB, name: Optional[str] = None
    ) -> None:
        """Add exclude pattern.

        Args:
            pattern: Pattern string
            pattern_type: Type of pattern (glob or regex)
            name: Optional pattern name
        """
        if pattern_type == PatternType.GLOB:
            self._exclude.add_glob_pattern(pattern, name)
        else:
            self._exclude.add_regex_pattern(pattern, name)

    def matches(self, path: str) -> bool:
        """Check if path should be included.

        Logic:
        1. If matches any exclude pattern → False
        2. If no include patterns → True (default allow)
        3. If matches any include pattern → True
        4. Otherwise → False

        Args:
            path: File path to check

        Returns:
            True if path should be included
        """
        # First check exclude patterns
        if self._exclude.matches(path):
            return False

        # If no include patterns, default to allow
        if not self._include:
            return True

        # Check include patterns
        return self._include.matches(path)

    def get_include_matcher(self) -> PatternMatcher:
        """Get include pattern matcher.

        Returns:
            Include pattern matcher
        """
        return self._include

    def get_exclude_matcher(self) -> PatternMatcher:
        """Get exclude pattern matcher.

        Returns:
            Exclude pattern matcher
        """
        return self._exclude

    def clear(self) -> None:
        """Clear all patterns."""
        self._include.clear()
        self._exclude.clear()
