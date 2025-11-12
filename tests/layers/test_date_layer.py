"""
Tests for ShadowFS DateLayer.

Tests date-based virtual layers with YYYY/MM/DD hierarchy.
Target: 90%+ coverage, 40+ tests
"""

import stat
from datetime import datetime
from unittest.mock import patch

import pytest

from shadowfs.layers.base import FileInfo
from shadowfs.layers.date import DateLayer


class TestDateLayerBasics:
    """Test DateLayer basic functionality."""

    def test_create_date_layer_default(self):
        """Test creating a DateLayer with default date field."""
        layer = DateLayer("by-date")

        assert layer.name == "by-date"
        assert layer.date_field == "mtime"
        assert layer.index == {}

    def test_create_date_layer_with_mtime(self):
        """Test creating a DateLayer with mtime field."""
        layer = DateLayer("by-modified", date_field="mtime")

        assert layer.name == "by-modified"
        assert layer.date_field == "mtime"

    def test_create_date_layer_with_ctime(self):
        """Test creating a DateLayer with ctime field."""
        layer = DateLayer("by-created", date_field="ctime")

        assert layer.name == "by-created"
        assert layer.date_field == "ctime"

    def test_create_date_layer_with_atime(self):
        """Test creating a DateLayer with atime field."""
        layer = DateLayer("by-accessed", date_field="atime")

        assert layer.name == "by-accessed"
        assert layer.date_field == "atime"

    def test_build_index_with_empty_list(self):
        """Test building index with no files."""
        layer = DateLayer("by-date")

        layer.build_index([])

        assert layer.index == {}

    def test_build_index_with_single_file(self):
        """Test building index with one file."""
        layer = DateLayer("by-date")

        # Create file with timestamp: 2024-11-12 12:00:00
        timestamp = datetime(2024, 11, 12, 12, 0, 0).timestamp()
        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=timestamp,
                ctime=timestamp,
                atime=timestamp,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert "2024" in layer.index
        assert "11" in layer.index["2024"]
        assert "12" in layer.index["2024"]["11"]
        assert len(layer.index["2024"]["11"]["12"]) == 1
        assert layer.index["2024"]["11"]["12"][0].name == "test.txt"

    def test_build_index_with_multiple_files_same_day(self):
        """Test building index with multiple files on same day."""
        layer = DateLayer("by-date")

        timestamp = datetime(2024, 11, 12, 12, 0, 0).timestamp()
        files = [
            FileInfo(
                name=f"file{i}.txt",
                path=f"file{i}.txt",
                real_path=f"/file{i}.txt",
                extension=".txt",
                size=100,
                mtime=timestamp,
                ctime=timestamp,
                atime=timestamp,
                mode=stat.S_IFREG | 0o644,
            )
            for i in range(3)
        ]

        layer.build_index(files)

        assert len(layer.index["2024"]["11"]["12"]) == 3

    def test_build_index_with_multiple_days(self):
        """Test building index with files across different days."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 13).timestamp(),
                ctime=datetime(2024, 11, 13).timestamp(),
                atime=datetime(2024, 11, 13).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "12" in layer.index["2024"]["11"]
        assert "13" in layer.index["2024"]["11"]
        assert len(layer.index["2024"]["11"]["12"]) == 1
        assert len(layer.index["2024"]["11"]["13"]) == 1

    def test_build_index_with_multiple_months(self):
        """Test building index with files across different months."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 10, 15).timestamp(),
                ctime=datetime(2024, 10, 15).timestamp(),
                atime=datetime(2024, 10, 15).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "10" in layer.index["2024"]
        assert "11" in layer.index["2024"]

    def test_build_index_with_multiple_years(self):
        """Test building index with files across different years."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 12, 25).timestamp(),
                ctime=datetime(2023, 12, 25).timestamp(),
                atime=datetime(2023, 12, 25).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "2023" in layer.index
        assert "2024" in layer.index

    def test_build_index_skips_directories(self):
        """Test that build_index skips directories."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="dir",
                path="dir",
                real_path="/dir",
                extension="",
                size=4096,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFDIR | 0o755,  # Directory
            )
        ]

        layer.build_index(files)

        assert layer.index == {}

    def test_build_index_clears_existing_index(self):
        """Test that build_index clears previous index."""
        layer = DateLayer("by-date")

        # Build first index
        files1 = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files1)
        assert "2024" in layer.index

        # Build second index with different date
        files2 = [
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 10, 10).timestamp(),
                ctime=datetime(2023, 10, 10).timestamp(),
                atime=datetime(2023, 10, 10).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files2)

        # Old date should be gone
        assert "2024" not in layer.index
        assert "2023" in layer.index


class TestDateLayerDateFields:
    """Test DateLayer with different date fields."""

    def test_index_by_mtime(self):
        """Test indexing by modification time."""
        layer = DateLayer("by-modified", date_field="mtime")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2023, 1, 1).timestamp(),  # Different
                atime=datetime(2023, 1, 1).timestamp(),  # Different
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Should be indexed by mtime (2024-11-12), not ctime/atime
        assert "2024" in layer.index
        assert "11" in layer.index["2024"]
        assert "12" in layer.index["2024"]["11"]

    def test_index_by_ctime(self):
        """Test indexing by creation time."""
        layer = DateLayer("by-created", date_field="ctime")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 1, 1).timestamp(),  # Different
                ctime=datetime(2024, 10, 15).timestamp(),
                atime=datetime(2023, 1, 1).timestamp(),  # Different
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Should be indexed by ctime (2024-10-15), not mtime/atime
        assert "2024" in layer.index
        assert "10" in layer.index["2024"]
        assert "15" in layer.index["2024"]["10"]

    def test_index_by_atime(self):
        """Test indexing by access time."""
        layer = DateLayer("by-accessed", date_field="atime")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 1, 1).timestamp(),  # Different
                ctime=datetime(2023, 1, 1).timestamp(),  # Different
                atime=datetime(2024, 9, 20).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Should be indexed by atime (2024-09-20), not mtime/ctime
        assert "2024" in layer.index
        assert "09" in layer.index["2024"]
        assert "20" in layer.index["2024"]["09"]


class TestDateLayerResolve:
    """Test DateLayer path resolution."""

    def test_resolve_existing_file(self):
        """Test resolving an existing file."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/source/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("2024/11/12/test.txt")

        assert result == "/source/test.txt"

    def test_resolve_nonexistent_file(self):
        """Test resolving a file that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("2024/11/12/nonexistent.txt")

        assert result is None

    def test_resolve_nonexistent_year(self):
        """Test resolving with a year that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("2023/11/12/test.txt")

        assert result is None

    def test_resolve_nonexistent_month(self):
        """Test resolving with a month that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("2024/10/12/test.txt")

        assert result is None

    def test_resolve_nonexistent_day(self):
        """Test resolving with a day that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("2024/11/13/test.txt")

        assert result is None

    def test_resolve_invalid_path_too_few_parts(self):
        """Test resolving with too few path components."""
        layer = DateLayer("by-date")

        files = []
        layer.build_index(files)

        # Only year
        assert layer.resolve("2024") is None

        # Year and month
        assert layer.resolve("2024/11") is None

        # Year, month, and day (no filename)
        assert layer.resolve("2024/11/12") is None

    def test_resolve_invalid_path_too_many_parts(self):
        """Test resolving with too many path components."""
        layer = DateLayer("by-date")

        files = []
        layer.build_index(files)

        # Too many levels
        result = layer.resolve("2024/11/12/subdir/test.txt")

        assert result is None


class TestDateLayerListDirectory:
    """Test DateLayer directory listing."""

    def test_list_directory_root(self):
        """Test listing years at root."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 12, 25).timestamp(),
                ctime=datetime(2023, 12, 25).timestamp(),
                atime=datetime(2023, 12, 25).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("")

        assert result == ["2023", "2024"]  # Sorted

    def test_list_directory_year(self):
        """Test listing months in a year."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 10, 15).timestamp(),
                ctime=datetime(2024, 10, 15).timestamp(),
                atime=datetime(2024, 10, 15).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("2024")

        assert result == ["10", "11"]  # Sorted, zero-padded

    def test_list_directory_month(self):
        """Test listing days in a month."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 25).timestamp(),
                ctime=datetime(2024, 11, 25).timestamp(),
                atime=datetime(2024, 11, 25).timestamp(),
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("2024/11")

        assert result == ["12", "25"]  # Sorted, zero-padded

    def test_list_directory_day(self):
        """Test listing files in a day."""
        layer = DateLayer("by-date")

        timestamp = datetime(2024, 11, 12).timestamp()
        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=timestamp,
                ctime=timestamp,
                atime=timestamp,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=timestamp,
                ctime=timestamp,
                atime=timestamp,
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("2024/11/12")

        assert result == ["file1.txt", "file2.txt"]  # Sorted

    def test_list_directory_nonexistent_year(self):
        """Test listing a year that doesn't exist."""
        layer = DateLayer("by-date")

        files = []
        layer.build_index(files)

        result = layer.list_directory("2023")

        assert result == []

    def test_list_directory_nonexistent_month(self):
        """Test listing a month that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.list_directory("2024/10")

        assert result == []

    def test_list_directory_nonexistent_day(self):
        """Test listing a day that doesn't exist."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.list_directory("2024/11/13")

        assert result == []

    def test_list_directory_empty_index(self):
        """Test listing with empty index."""
        layer = DateLayer("by-date")

        layer.build_index([])

        result = layer.list_directory("")

        assert result == []

    def test_list_directory_invalid_depth(self):
        """Test listing with too many path components."""
        layer = DateLayer("by-date")

        files = []
        layer.build_index(files)

        # Too deep
        result = layer.list_directory("2024/11/12/extra")

        assert result == []


class TestDateLayerEdgeCases:
    """Test DateLayer edge cases."""

    def test_zero_padded_months_and_days(self):
        """Test that months and days are zero-padded."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 1, 5).timestamp(),  # Jan 5
                ctime=datetime(2024, 1, 5).timestamp(),
                atime=datetime(2024, 1, 5).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        # Check zero-padding
        assert "01" in layer.index["2024"]  # Month
        assert "05" in layer.index["2024"]["01"]  # Day

        # Verify can list with padding
        months = layer.list_directory("2024")
        assert "01" in months

        days = layer.list_directory("2024/01")
        assert "05" in days

    def test_leap_year_february_29(self):
        """Test handling of leap year Feb 29."""
        layer = DateLayer("by-date")

        files = [
            FileInfo(
                name="leap.txt",
                path="leap.txt",
                real_path="/leap.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 2, 29).timestamp(),  # Leap day
                ctime=datetime(2024, 2, 29).timestamp(),
                atime=datetime(2024, 2, 29).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        assert "29" in layer.index["2024"]["02"]

    def test_ancient_timestamp_handled(self):
        """Test that files with ancient timestamps are handled correctly."""
        layer = DateLayer("by-date")

        # Negative timestamps are valid (dates near Unix epoch)
        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=-1.0,  # Near Unix epoch (timezone-dependent)
                ctime=-1.0,
                atime=-1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        # Should not raise exception
        layer.build_index(files)

        # File should be indexed (year may vary by timezone)
        assert len(layer.index) > 0

    def test_refresh_rebuilds_index(self):
        """Test that refresh() rebuilds the index."""
        layer = DateLayer("by-date")

        # Build initial index
        files1 = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files1)
        assert "2024" in layer.index

        # Refresh with new files
        files2 = [
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2023, 10, 10).timestamp(),
                ctime=datetime(2023, 10, 10).timestamp(),
                atime=datetime(2023, 10, 10).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.refresh(files2)

        # Old date should be gone, new date present
        assert "2024" not in layer.index
        assert "2023" in layer.index

    def test_repr(self):
        """Test string representation."""
        layer = DateLayer("by-date")

        result = repr(layer)

        assert "DateLayer" in result
        assert "by-date" in result

    def test_invalid_date_field_raises_error(self):
        """Test that invalid date_field raises ValueError."""
        layer = DateLayer("by-date")
        # Manually set invalid date_field to test error handling
        layer.date_field = "invalid"  # type: ignore

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=datetime(2024, 11, 12).timestamp(),
                ctime=datetime(2024, 11, 12).timestamp(),
                atime=datetime(2024, 11, 12).timestamp(),
                mode=stat.S_IFREG | 0o644,
            )
        ]

        # Should skip files with invalid date_field
        layer.build_index(files)

        # Index should be empty since file was skipped due to ValueError
        assert layer.index == {}
