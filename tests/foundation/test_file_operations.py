"""Tests for file operations module."""
import os
import stat
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, ANY
import hashlib

import pytest

from shadowfs.foundation.constants import ErrorCode, FileAttributes, Limits
from shadowfs.foundation.file_operations import (
    FileOperationError,
    read_file,
    write_file,
    delete_file,
    copy_file,
    move_file,
    get_file_attributes,
    file_exists,
    is_readable,
    is_writable,
    is_executable,
    create_directory,
    list_directory,
    open_file,
    calculate_checksum,
    set_permissions,
    create_symlink,
)


class TestFileOperationError:
    """Test FileOperationError exception."""

    def test_error_with_message(self):
        """Test error with message only."""
        error = FileOperationError("Test error")
        assert str(error) == "Test error"
        assert error.error_code == ErrorCode.INTERNAL_ERROR

    def test_error_with_code(self):
        """Test error with custom error code."""
        error = FileOperationError("Not found", ErrorCode.NOT_FOUND)
        assert str(error) == "Not found"
        assert error.error_code == ErrorCode.NOT_FOUND


class TestReadFile:
    """Test read_file function."""

    def test_read_binary_file(self):
        """Test reading file in binary mode."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            content = read_file(tmp_path, binary=True)
            assert content == b"test content"
            assert isinstance(content, bytes)
        finally:
            os.unlink(tmp_path)

    def test_read_text_file(self):
        """Test reading file in text mode."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            content = read_file(tmp_path, binary=False)
            assert content == "test content"
            assert isinstance(content, str)
        finally:
            os.unlink(tmp_path)

    def test_read_with_size_limit(self):
        """Test reading file with size limit."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"x" * 50)
            tmp_path = tmp.name

        try:
            # File is within size limit, so it should be read completely
            content = read_file(tmp_path, size_limit=100)
            assert len(content) == 50
        finally:
            os.unlink(tmp_path)

    def test_read_exceeds_size_limit(self):
        """Test reading file that exceeds size limit."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"x" * 1000)
            tmp_path = tmp.name

        try:
            with pytest.raises(FileOperationError) as exc_info:
                read_file(tmp_path, size_limit=100)
            assert "exceeds limit" in str(exc_info.value)
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        finally:
            os.unlink(tmp_path)

    def test_read_file_not_found(self):
        """Test reading non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            read_file("/nonexistent/file.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_read_permission_denied(self):
        """Test reading file with no permissions."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"content")
            tmp_path = tmp.name

        try:
            os.chmod(tmp_path, 0o000)
            with pytest.raises(FileOperationError) as exc_info:
                read_file(tmp_path)
            assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
        finally:
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)

    def test_read_io_error(self):
        """Test read with IO error."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Mock open to raise IOError after file exists check passes
            with patch('builtins.open', side_effect=IOError("IO error")):
                with pytest.raises(FileOperationError) as exc_info:
                    read_file(tmp_path)
                assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR
        finally:
            os.unlink(tmp_path)


class TestWriteFile:
    """Test write_file function."""

    def test_write_binary_file(self):
        """Test writing binary content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.bin")
            write_file(file_path, b"binary content", binary=True)

            with open(file_path, 'rb') as f:
                assert f.read() == b"binary content"

    def test_write_text_file(self):
        """Test writing text content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            write_file(file_path, "text content", binary=False)

            with open(file_path, 'r') as f:
                assert f.read() == "text content"

    def test_write_atomic(self):
        """Test atomic write with temp file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")

            # Write initial content
            write_file(file_path, "initial", binary=False, atomic=True)

            # Verify atomic write by checking temp file usage
            with open(file_path, 'r') as f:
                assert f.read() == "initial"

            # Write new content atomically
            write_file(file_path, "new content", binary=False, atomic=True)

            with open(file_path, 'r') as f:
                assert f.read() == "new content"

    def test_write_non_atomic(self):
        """Test non-atomic direct write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            write_file(file_path, "content", binary=False, atomic=False)

            with open(file_path, 'r') as f:
                assert f.read() == "content"

    def test_write_create_dirs(self):
        """Test creating parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "subdir", "nested", "test.txt")
            write_file(file_path, "content", binary=False, create_dirs=True)

            assert os.path.exists(file_path)
            with open(file_path, 'r') as f:
                assert f.read() == "content"

    def test_write_permission_denied(self):
        """Test write with permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o444)  # Read-only
            file_path = os.path.join(tmpdir, "test.txt")

            try:
                with pytest.raises(FileOperationError) as exc_info:
                    write_file(file_path, "content", binary=False)
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
            finally:
                os.chmod(tmpdir, 0o755)

    def test_write_io_error(self):
        """Test write with IO error."""
        with patch('builtins.open', side_effect=IOError("IO error")):
            with pytest.raises(FileOperationError) as exc_info:
                write_file("/some/file.txt", "content", atomic=False)
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestDeleteFile:
    """Test delete_file function."""

    def test_delete_regular_file(self):
        """Test deleting a regular file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        delete_file(tmp_path)
        assert not os.path.exists(tmp_path)

    def test_delete_safe_mode_prevents_symlink(self):
        """Test safe mode prevents deleting symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")
            os.symlink(target, link)

            with pytest.raises(FileOperationError) as exc_info:
                delete_file(link, safe=True)
            assert "Cannot delete symlink" in str(exc_info.value)
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    def test_delete_safe_mode_prevents_directory(self):
        """Test safe mode prevents deleting directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.mkdir(subdir)

            with pytest.raises(FileOperationError) as exc_info:
                delete_file(subdir, safe=True)
            assert "Not a regular file" in str(exc_info.value)
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    def test_delete_unsafe_mode(self):
        """Test unsafe mode allows deleting anything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")
            os.symlink(target, link)

            delete_file(link, safe=False)
            assert not os.path.exists(link)
            assert os.path.exists(target)  # Target still exists

    def test_delete_file_not_found(self):
        """Test deleting non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            delete_file("/nonexistent/file.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_delete_permission_denied(self):
        """Test delete with permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            with open(file_path, 'w') as f:
                f.write("content")

            os.chmod(tmpdir, 0o444)  # Read-only directory
            try:
                with pytest.raises(FileOperationError) as exc_info:
                    delete_file(file_path)
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
            finally:
                os.chmod(tmpdir, 0o755)

    def test_delete_io_error(self):
        """Test delete with IO error."""
        with patch('os.unlink', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                delete_file("/some/file.txt", safe=False)
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestCopyFile:
    """Test copy_file function."""

    def test_copy_file_basic(self):
        """Test basic file copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("content")

            copy_file(source, dest)

            assert os.path.exists(dest)
            with open(dest, 'r') as f:
                assert f.read() == "content"

    def test_copy_preserve_metadata(self):
        """Test copying with metadata preservation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("content")
            os.chmod(source, 0o600)

            copy_file(source, dest, preserve_metadata=True)

            source_stat = os.stat(source)
            dest_stat = os.stat(dest)
            assert stat.S_IMODE(dest_stat.st_mode) == 0o600

    def test_copy_without_metadata(self):
        """Test copying without metadata preservation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("content")

            copy_file(source, dest, preserve_metadata=False)
            assert os.path.exists(dest)

    def test_copy_overwrite_false(self):
        """Test copy fails when destination exists and overwrite=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("source content")
            with open(dest, 'w') as f:
                f.write("dest content")

            with pytest.raises(FileOperationError) as exc_info:
                copy_file(source, dest, overwrite=False)
            assert exc_info.value.error_code == ErrorCode.CONFLICT

    def test_copy_overwrite_true(self):
        """Test copy succeeds when destination exists and overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("source content")
            with open(dest, 'w') as f:
                f.write("dest content")

            copy_file(source, dest, overwrite=True)

            with open(dest, 'r') as f:
                assert f.read() == "source content"

    def test_copy_source_not_found(self):
        """Test copy with non-existent source."""
        with pytest.raises(FileOperationError) as exc_info:
            copy_file("/nonexistent/source.txt", "/tmp/dest.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_copy_permission_denied(self):
        """Test copy with permission denied."""
        with tempfile.NamedTemporaryFile() as tmp:
            with patch('shutil.copy2', side_effect=PermissionError("Permission denied")):
                with pytest.raises(FileOperationError) as exc_info:
                    copy_file(tmp.name, "/dest.txt")
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED

    def test_copy_shutil_error(self):
        """Test copy with shutil error."""
        with patch('shutil.copy2', side_effect=shutil.Error("Shutil error")):
            with tempfile.NamedTemporaryFile() as tmp:
                with pytest.raises(FileOperationError) as exc_info:
                    copy_file(tmp.name, "/dest.txt")
                assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestMoveFile:
    """Test move_file function."""

    def test_move_file_basic(self):
        """Test basic file move."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("content")

            move_file(source, dest)

            assert not os.path.exists(source)
            assert os.path.exists(dest)
            with open(dest, 'r') as f:
                assert f.read() == "content"

    def test_move_overwrite_false(self):
        """Test move fails when destination exists and overwrite=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("source content")
            with open(dest, 'w') as f:
                f.write("dest content")

            with pytest.raises(FileOperationError) as exc_info:
                move_file(source, dest, overwrite=False)
            assert exc_info.value.error_code == ErrorCode.CONFLICT

    def test_move_overwrite_true(self):
        """Test move succeeds when destination exists and overwrite=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            dest = os.path.join(tmpdir, "dest.txt")

            with open(source, 'w') as f:
                f.write("source content")
            with open(dest, 'w') as f:
                f.write("dest content")

            move_file(source, dest, overwrite=True)

            assert not os.path.exists(source)
            with open(dest, 'r') as f:
                assert f.read() == "source content"

    def test_move_source_not_found(self):
        """Test move with non-existent source."""
        with pytest.raises(FileOperationError) as exc_info:
            move_file("/nonexistent/source.txt", "/tmp/dest.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_move_permission_denied(self):
        """Test move with permission denied."""
        with tempfile.NamedTemporaryFile() as tmp:
            with patch('shutil.move', side_effect=PermissionError("Permission denied")):
                with pytest.raises(FileOperationError) as exc_info:
                    move_file(tmp.name, "/dest.txt")
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED

    def test_move_shutil_error(self):
        """Test move with shutil error."""
        with patch('shutil.move', side_effect=shutil.Error("Shutil error")):
            with tempfile.NamedTemporaryFile() as tmp:
                with pytest.raises(FileOperationError) as exc_info:
                    move_file(tmp.name, "/dest.txt")
                assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestGetFileAttributes:
    """Test get_file_attributes function."""

    def test_get_attributes_regular_file(self):
        """Test getting attributes of regular file."""
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(b"content")
            tmp.flush()

            attrs = get_file_attributes(tmp.name)

            assert isinstance(attrs, FileAttributes)
            assert attrs.st_size == 7
            assert attrs.is_file
            assert not attrs.is_dir
            assert not attrs.is_symlink

    def test_get_attributes_directory(self):
        """Test getting attributes of directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            attrs = get_file_attributes(tmpdir)

            assert isinstance(attrs, FileAttributes)
            assert attrs.is_dir
            assert not attrs.is_file
            assert not attrs.is_symlink

    def test_get_attributes_symlink_follow(self):
        """Test getting attributes of symlink with follow=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")
            os.symlink(target, link)

            attrs = get_file_attributes(link, follow_symlinks=True)
            assert attrs.is_file  # Points to file
            assert not attrs.is_symlink

    def test_get_attributes_symlink_no_follow(self):
        """Test getting attributes of symlink with follow=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")
            os.symlink(target, link)

            attrs = get_file_attributes(link, follow_symlinks=False)
            assert attrs.is_symlink

    def test_get_attributes_not_found(self):
        """Test getting attributes of non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            get_file_attributes("/nonexistent/file.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_get_attributes_permission_denied(self):
        """Test getting attributes with permission denied."""
        with patch('os.stat', side_effect=PermissionError("Permission denied")):
            with pytest.raises(FileOperationError) as exc_info:
                get_file_attributes("/some/file.txt")
            assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED

    def test_get_attributes_io_error(self):
        """Test getting attributes with IO error."""
        with patch('os.stat', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                get_file_attributes("/some/file.txt")
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestFileChecks:
    """Test file existence and permission checks."""

    def test_file_exists_true(self):
        """Test file_exists returns True for existing file."""
        with tempfile.NamedTemporaryFile() as tmp:
            assert file_exists(tmp.name) is True

    def test_file_exists_false(self):
        """Test file_exists returns False for non-existent file."""
        assert file_exists("/nonexistent/file.txt") is False

    def test_file_exists_with_path_error(self):
        """Test file_exists returns False on path error."""
        with patch('shadowfs.foundation.path_utils.normalize_path', side_effect=Exception("Error")):
            assert file_exists("/some/path") is False

    def test_is_readable_true(self):
        """Test is_readable returns True for readable file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o644)
            assert is_readable(tmp.name) is True

    def test_is_readable_false(self):
        """Test is_readable returns False for unreadable file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o000)
            result = is_readable(tmp.name)
            os.chmod(tmp.name, 0o644)  # Restore for cleanup
            assert result is False

    def test_is_readable_nonexistent(self):
        """Test is_readable returns False for non-existent file."""
        assert is_readable("/nonexistent/file.txt") is False

    def test_is_writable_true(self):
        """Test is_writable returns True for writable file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o644)
            assert is_writable(tmp.name) is True

    def test_is_writable_false(self):
        """Test is_writable returns False for read-only file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o444)
            result = is_writable(tmp.name)
            os.chmod(tmp.name, 0o644)  # Restore for cleanup
            assert result is False

    def test_is_writable_nonexistent(self):
        """Test is_writable returns False for non-existent file."""
        assert is_writable("/nonexistent/file.txt") is False

    def test_is_executable_true(self):
        """Test is_executable returns True for executable file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o755)
            assert is_executable(tmp.name) is True

    def test_is_executable_false(self):
        """Test is_executable returns False for non-executable file."""
        with tempfile.NamedTemporaryFile() as tmp:
            os.chmod(tmp.name, 0o644)
            assert is_executable(tmp.name) is False

    def test_is_executable_nonexistent(self):
        """Test is_executable returns False for non-existent file."""
        assert is_executable("/nonexistent/file.txt") is False


class TestCreateDirectory:
    """Test create_directory function."""

    def test_create_single_directory(self):
        """Test creating a single directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")
            create_directory(new_dir)
            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)

    def test_create_with_mode(self):
        """Test creating directory with specific mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")
            create_directory(new_dir, mode=0o700)
            assert os.path.exists(new_dir)
            mode = stat.S_IMODE(os.stat(new_dir).st_mode)
            # Mode might be affected by umask, so check it's at least not world-readable
            assert mode & 0o077 == 0

    def test_create_parents(self):
        """Test creating parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "parent", "child", "grandchild")
            create_directory(new_dir, parents=True)
            assert os.path.exists(new_dir)

    def test_create_no_parents_fails(self):
        """Test creating directory without parents fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "parent", "child")
            with pytest.raises(FileOperationError):
                create_directory(new_dir, parents=False)

    def test_create_exist_ok_true(self):
        """Test creating existing directory with exist_ok=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")
            os.mkdir(new_dir)
            create_directory(new_dir, exist_ok=True)  # Should not raise

    def test_create_exist_ok_false(self):
        """Test creating existing directory with exist_ok=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")
            os.mkdir(new_dir)
            with pytest.raises(FileOperationError) as exc_info:
                create_directory(new_dir, exist_ok=False)
            assert exc_info.value.error_code == ErrorCode.CONFLICT

    def test_create_permission_denied(self):
        """Test create with permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o444)  # Read-only
            new_dir = os.path.join(tmpdir, "newdir")

            try:
                with pytest.raises(FileOperationError) as exc_info:
                    create_directory(new_dir)
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
            finally:
                os.chmod(tmpdir, 0o755)

    def test_create_io_error(self):
        """Test create with IO error."""
        with patch('os.makedirs', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                create_directory("/some/dir")
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestListDirectory:
    """Test list_directory function."""

    def test_list_directory_basic(self):
        """Test listing directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            open(os.path.join(tmpdir, "file1.txt"), 'w').close()
            open(os.path.join(tmpdir, "file2.txt"), 'w').close()
            os.mkdir(os.path.join(tmpdir, "subdir"))

            entries = list_directory(tmpdir)
            assert len(entries) == 3
            assert "file1.txt" in entries
            assert "file2.txt" in entries
            assert "subdir" in entries

    def test_list_directory_exclude_hidden(self):
        """Test listing directory excluding hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "file.txt"), 'w').close()
            open(os.path.join(tmpdir, ".hidden"), 'w').close()

            entries = list_directory(tmpdir, include_hidden=False)
            assert "file.txt" in entries
            assert ".hidden" not in entries

    def test_list_directory_include_hidden(self):
        """Test listing directory including hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "file.txt"), 'w').close()
            open(os.path.join(tmpdir, ".hidden"), 'w').close()

            entries = list_directory(tmpdir, include_hidden=True)
            assert "file.txt" in entries
            assert ".hidden" in entries

    def test_list_directory_sorted(self):
        """Test directory entries are sorted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "zebra.txt"), 'w').close()
            open(os.path.join(tmpdir, "alpha.txt"), 'w').close()
            open(os.path.join(tmpdir, "beta.txt"), 'w').close()

            entries = list_directory(tmpdir)
            assert entries == ["alpha.txt", "beta.txt", "zebra.txt"]

    def test_list_directory_not_found(self):
        """Test listing non-existent directory."""
        with pytest.raises(FileOperationError) as exc_info:
            list_directory("/nonexistent/dir")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_list_not_a_directory(self):
        """Test listing a file instead of directory."""
        with tempfile.NamedTemporaryFile() as tmp:
            with pytest.raises(FileOperationError) as exc_info:
                list_directory(tmp.name)
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    def test_list_permission_denied(self):
        """Test listing directory with no permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o000)
            try:
                with pytest.raises(FileOperationError) as exc_info:
                    list_directory(tmpdir)
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
            finally:
                os.chmod(tmpdir, 0o755)

    def test_list_io_error(self):
        """Test listing with IO error."""
        with patch('os.listdir', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                list_directory("/some/dir")
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestOpenFile:
    """Test open_file context manager."""

    def test_open_file_read_text(self):
        """Test opening file for reading text."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            with open_file(tmp_path, 'r') as f:
                content = f.read()
                assert content == "test content"
        finally:
            os.unlink(tmp_path)

    def test_open_file_write_text(self):
        """Test opening file for writing text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")

            with open_file(file_path, 'w') as f:
                f.write("test content")

            with open(file_path, 'r') as f:
                assert f.read() == "test content"

    def test_open_file_read_binary(self):
        """Test opening file for reading binary."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"binary content")
            tmp_path = tmp.name

        try:
            with open_file(tmp_path, 'rb', encoding=None) as f:
                content = f.read()
                assert content == b"binary content"
        finally:
            os.unlink(tmp_path)

    def test_open_file_with_encoding(self):
        """Test opening file with specific encoding."""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as tmp:
            tmp.write("Unicode: ñ")
            tmp_path = tmp.name

        try:
            with open_file(tmp_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert content == "Unicode: ñ"
        finally:
            os.unlink(tmp_path)

    def test_open_file_not_found(self):
        """Test opening non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            with open_file("/nonexistent/file.txt", 'r') as f:
                pass
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_open_file_permission_denied(self):
        """Test opening file with no permissions."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            os.chmod(tmp_path, 0o000)
            with pytest.raises(FileOperationError) as exc_info:
                with open_file(tmp_path, 'r') as f:
                    pass
            assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
        finally:
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)

    def test_open_file_io_error(self):
        """Test opening file with IO error."""
        with patch('builtins.open', side_effect=IOError("IO error")):
            with pytest.raises(FileOperationError) as exc_info:
                with open_file("/some/file.txt", 'r') as f:
                    pass
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR

    def test_open_file_closes_on_error(self):
        """Test file is closed even on error."""
        mock_file = MagicMock()
        with patch('builtins.open', return_value=mock_file):
            try:
                with open_file("/some/file.txt", 'r') as f:
                    raise RuntimeError("Test error")
            except RuntimeError:
                pass
            mock_file.close.assert_called_once()


class TestCalculateChecksum:
    """Test calculate_checksum function."""

    def test_checksum_sha256(self):
        """Test calculating SHA256 checksum."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            checksum = calculate_checksum(tmp_path, algorithm="sha256")
            expected = hashlib.sha256(b"test content").hexdigest()
            assert checksum == expected
        finally:
            os.unlink(tmp_path)

    def test_checksum_md5(self):
        """Test calculating MD5 checksum."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            checksum = calculate_checksum(tmp_path, algorithm="md5")
            expected = hashlib.md5(b"test content").hexdigest()
            assert checksum == expected
        finally:
            os.unlink(tmp_path)

    def test_checksum_sha1(self):
        """Test calculating SHA1 checksum."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            checksum = calculate_checksum(tmp_path, algorithm="sha1")
            expected = hashlib.sha1(b"test content").hexdigest()
            assert checksum == expected
        finally:
            os.unlink(tmp_path)

    def test_checksum_large_file(self):
        """Test calculating checksum of large file with chunks."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Write large content
            content = b"x" * 100000
            tmp.write(content)
            tmp_path = tmp.name

        try:
            checksum = calculate_checksum(tmp_path, chunk_size=8192)
            expected = hashlib.sha256(content).hexdigest()
            assert checksum == expected
        finally:
            os.unlink(tmp_path)

    def test_checksum_invalid_algorithm(self):
        """Test checksum with invalid algorithm."""
        with tempfile.NamedTemporaryFile() as tmp:
            with pytest.raises(FileOperationError) as exc_info:
                calculate_checksum(tmp.name, algorithm="invalid")
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    def test_checksum_file_not_found(self):
        """Test checksum of non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            calculate_checksum("/nonexistent/file.txt")
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_checksum_permission_denied(self):
        """Test checksum with no permissions."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            os.chmod(tmp_path, 0o000)
            with pytest.raises(FileOperationError) as exc_info:
                calculate_checksum(tmp_path)
            assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
        finally:
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)

    def test_checksum_io_error(self):
        """Test checksum with IO error."""
        with patch('builtins.open', side_effect=IOError("IO error")):
            with pytest.raises(FileOperationError) as exc_info:
                calculate_checksum("/some/file.txt")
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestSetPermissions:
    """Test set_permissions function."""

    def test_set_permissions_basic(self):
        """Test setting file permissions."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            set_permissions(tmp_path, 0o600)
            mode = stat.S_IMODE(os.stat(tmp_path).st_mode)
            assert mode == 0o600
        finally:
            os.unlink(tmp_path)

    def test_set_permissions_executable(self):
        """Test setting executable permissions."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            set_permissions(tmp_path, 0o755)
            mode = stat.S_IMODE(os.stat(tmp_path).st_mode)
            assert mode == 0o755
        finally:
            os.unlink(tmp_path)

    def test_set_permissions_not_found(self):
        """Test setting permissions on non-existent file."""
        with pytest.raises(FileOperationError) as exc_info:
            set_permissions("/nonexistent/file.txt", 0o644)
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_set_permissions_denied(self):
        """Test setting permissions with permission denied."""
        with patch('os.chmod', side_effect=PermissionError("Permission denied")):
            with pytest.raises(FileOperationError) as exc_info:
                set_permissions("/some/file.txt", 0o644)
            assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED

    def test_set_permissions_io_error(self):
        """Test setting permissions with IO error."""
        with patch('os.chmod', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                set_permissions("/some/file.txt", 0o644)
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR


class TestCreateSymlink:
    """Test create_symlink function."""

    def test_create_symlink_basic(self):
        """Test creating a basic symlink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")

            create_symlink(target, link)

            assert os.path.islink(link)
            assert os.readlink(link) == target

    def test_create_symlink_to_directory(self):
        """Test creating symlink to directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = os.path.join(tmpdir, "target_dir")
            link = os.path.join(tmpdir, "link_dir")

            os.mkdir(target_dir)
            create_symlink(target_dir, link)

            assert os.path.islink(link)
            assert os.readlink(link) == target_dir

    def test_create_symlink_exists(self):
        """Test creating symlink when link already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            link = os.path.join(tmpdir, "link.txt")

            with open(target, 'w') as f:
                f.write("content")
            with open(link, 'w') as f:
                f.write("existing")

            with pytest.raises(FileOperationError) as exc_info:
                create_symlink(target, link)
            assert exc_info.value.error_code == ErrorCode.CONFLICT

    def test_create_symlink_permission_denied(self):
        """Test creating symlink with permission denied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chmod(tmpdir, 0o444)  # Read-only
            target = "/tmp/target"
            link = os.path.join(tmpdir, "link")

            try:
                with pytest.raises(FileOperationError) as exc_info:
                    create_symlink(target, link)
                assert exc_info.value.error_code == ErrorCode.PERMISSION_DENIED
            finally:
                os.chmod(tmpdir, 0o755)

    def test_create_symlink_io_error(self):
        """Test creating symlink with IO error."""
        with patch('os.symlink', side_effect=OSError("OS error")):
            with pytest.raises(FileOperationError) as exc_info:
                create_symlink("/target", "/link")
            assert exc_info.value.error_code == ErrorCode.INTERNAL_ERROR