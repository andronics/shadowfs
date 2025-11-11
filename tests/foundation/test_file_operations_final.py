#!/usr/bin/env python3
"""Final tests to achieve 100% coverage for file_operations.py."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open
import errno

from shadowfs.foundation.file_operations import (
    FileOperationError,
    write_file,
    delete_file,
    create_directory,
    open_file,
)
from shadowfs.foundation.constants import ErrorCode


class TestFinalCoverage:
    """Final tests to cover remaining lines."""

    def test_write_file_create_dirs_exists_already(self):
        """Test write_file with create_dirs when parent dir already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create parent directory first
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)

            # Now write file with create_dirs=True (should skip creating)
            test_file = os.path.join(subdir, "file.txt")
            write_file(test_file, b"content", create_dirs=True)

            # Verify file was written
            with open(test_file, 'rb') as f:
                assert f.read() == b"content"

    def test_delete_file_unsafe_empty_path(self):
        """Test delete_file with empty path in unsafe mode."""
        with pytest.raises(FileOperationError) as exc_info:
            delete_file("", safe=False)
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Path cannot be empty" in str(exc_info.value)

    def test_create_directory_simple_exist_ok_true(self):
        """Test create_directory with simple path when exist_ok=True and dir exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory
            test_dir = os.path.join(tmpdir, "testdir")
            os.mkdir(test_dir)

            # Try to create it again with exist_ok=True (should return early)
            create_directory(test_dir, exist_ok=True, parents=False)

            # Verify directory still exists
            assert os.path.isdir(test_dir)

    def test_create_directory_conflict_exist_ok_false(self):
        """Test create_directory raises FileExistsError when exist_ok=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "testdir")

            # First create the directory
            create_directory(test_dir, exist_ok=False, parents=False)

            # Try to create it again with exist_ok=False
            with pytest.raises(FileOperationError) as exc_info:
                create_directory(test_dir, exist_ok=False, parents=False)
            assert exc_info.value.error_code == ErrorCode.CONFLICT
            assert "Directory already exists" in str(exc_info.value)

    def test_open_file_close_error_ignored(self):
        """Test open_file context manager ignores close errors."""
        # Create a mock file that raises error on close
        mock_file = MagicMock()
        mock_file.close.side_effect = OSError("Close failed")

        with patch('builtins.open', return_value=mock_file):
            # This should not raise even though close fails
            with open_file("/fake/path", 'r') as f:
                pass  # File opened and used

            # Verify close was attempted
            mock_file.close.assert_called_once()