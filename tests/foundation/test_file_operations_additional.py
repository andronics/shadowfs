#!/usr/bin/env python3
"""Additional tests to achieve 100% coverage for file_operations.py."""

import errno
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.foundation.constants import ErrorCode
from shadowfs.foundation.file_operations import (
    FileOperationError,
    create_directory,
    delete_file,
    file_exists,
    get_file_attributes,
    is_executable,
    is_readable,
    is_writable,
    open_file,
    write_file,
)


class TestAdditionalCoverage:
    """Tests to cover remaining uncovered lines."""

    def test_write_file_create_dirs_oserror(self):
        """Test write_file when makedirs raises OSError (not EEXIST)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "subdir", "file.txt")

            # Mock makedirs to raise OSError with errno != EEXIST
            with patch("os.makedirs") as mock_makedirs:
                error = OSError("Some other error")
                error.errno = errno.EACCES  # Not EEXIST
                mock_makedirs.side_effect = error

                with pytest.raises(FileOperationError) as exc_info:
                    write_file(test_file, b"content", create_dirs=True)
                assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR

    def test_delete_file_unsafe_mode_oserror(self):
        """Test delete_file in unsafe mode when unlink raises generic OSError."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"content")

        try:
            with patch("os.unlink") as mock_unlink:
                mock_unlink.side_effect = OSError("Generic error")

                with pytest.raises(FileOperationError) as exc_info:
                    delete_file(tmp_path, safe=False)
                assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_get_attributes_empty_path(self):
        """Test get_file_attributes with empty path when not following symlinks."""
        with pytest.raises(FileOperationError) as exc_info:
            get_file_attributes("", follow_symlinks=False)
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Path cannot be empty" in str(exc_info.value)

    def test_is_readable_oserror(self):
        """Test is_readable when access raises OSError - should return False."""
        with patch("os.access") as mock_access:
            mock_access.side_effect = OSError("Generic error")

            # Should return False when OSError is raised
            assert is_readable("/some/path") == False

    def test_is_writable_oserror(self):
        """Test is_writable when access raises OSError - should return False."""
        with patch("os.access") as mock_access:
            mock_access.side_effect = OSError("Generic error")

            # Should return False when OSError is raised
            assert is_writable("/some/path") == False

    def test_is_executable_oserror(self):
        """Test is_executable when access raises OSError - should return False."""
        with patch("os.access") as mock_access:
            mock_access.side_effect = OSError("Generic error")

            # Should return False when OSError is raised
            assert is_executable("/some/path") == False

    def test_file_exists_oserror(self):
        """Test file_exists when exists raises OSError - should return False."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = OSError("Generic error")

            # Should return False when OSError is raised
            assert file_exists("/some/path") == False

    def test_create_directory_oserror(self):
        """Test create_directory when makedirs raises generic OSError."""
        with patch("os.makedirs") as mock_makedirs:
            # Raise OSError with errno != EEXIST
            error = OSError("Generic error")
            error.errno = errno.EACCES
            mock_makedirs.side_effect = error

            with pytest.raises(FileOperationError) as exc_info:
                create_directory("/some/dir", exist_ok=True)
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR

    def test_open_file_context_manager_exception(self):
        """Test open_file context manager when exception occurs in with block."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"content")

        try:
            # Test that file handle is properly closed even when exception occurs
            with pytest.raises(ValueError):
                with open_file(tmp_path, "r") as f:
                    # Verify file is open
                    assert not f.closed
                    # Raise exception
                    raise ValueError("Test exception")

            # File should be closed after exiting context manager
            # (We can't directly check this, but the test verifies the __exit__ path)
        finally:
            os.unlink(tmp_path)

    def test_open_file_write_mode(self):
        """Test open_file in write mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")

            with open_file(test_file, "w") as f:
                f.write("test content")

            # Verify content was written
            with open(test_file, "r") as f:
                assert f.read() == "test content"
