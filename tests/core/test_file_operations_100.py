#!/usr/bin/env python3
"""Tests to achieve 100% coverage for file_operations.py."""

import errno
import os
import tempfile
from unittest.mock import patch

import pytest

from shadowfs.core.constants import ErrorCode
from shadowfs.core.file_ops import FileOperationError, create_directory


class TestFinalBranchCoverage:
    """Test to cover the final missing branch."""

    def test_create_directory_exists_with_exist_ok_true_parents(self):
        """Test create_directory with parents=True when dir exists and exist_ok=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "subdir", "testdir")

            # Create the full directory path
            os.makedirs(test_dir)

            # Now try to create it again with exist_ok=True and parents=True
            # This should hit the FileExistsError handler with exist_ok=True branch
            create_directory(test_dir, exist_ok=True, parents=True)

            # Verify directory still exists
            assert os.path.isdir(test_dir)

    def test_create_directory_makedirs_exists_error_with_exist_ok(self):
        """Test makedirs raising FileExistsError when exist_ok=True."""
        with patch("os.makedirs") as mock_makedirs:
            # Make makedirs raise FileExistsError
            mock_makedirs.side_effect = FileExistsError("Directory exists")

            # This should NOT raise an error when exist_ok=True
            # It should silently handle the FileExistsError
            create_directory("/some/path", exist_ok=True, parents=True)

            # Verify makedirs was called
            mock_makedirs.assert_called_once()
