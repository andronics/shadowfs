"""Tests for path utilities module."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from shadowfs.foundation.constants import ErrorCode, Limits
from shadowfs.foundation.path_utils import (
    PathError,
    normalize_path,
    is_safe_path,
    join_paths,
    split_path,
    get_parent_path,
    get_filename,
    get_extension,
    resolve_symlinks,
    validate_filename,
    is_absolute_path,
    make_relative,
    parse_virtual_path,
    is_hidden_file,
    list_path_components,
    common_path_prefix,
    ensure_trailing_slash,
    remove_trailing_slash,
)


class TestPathError:
    """Test PathError exception."""

    def test_path_error_with_message(self):
        """Test PathError with message only."""
        error = PathError("Test error")
        assert str(error) == "Test error"
        assert error.error_code == ErrorCode.INVALID_INPUT

    def test_path_error_with_error_code(self):
        """Test PathError with custom error code."""
        error = PathError("Not found", ErrorCode.NOT_FOUND)
        assert str(error) == "Not found"
        assert error.error_code == ErrorCode.NOT_FOUND


class TestNormalizePath:
    """Test path normalization."""

    def test_empty_path(self):
        """Empty path should raise error."""
        with pytest.raises(PathError) as exc_info:
            normalize_path("")
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    def test_path_too_long(self):
        """Path exceeding limit should raise error."""
        long_path = "a" * (Limits.MAX_PATH_LENGTH + 1)
        with pytest.raises(PathError) as exc_info:
            normalize_path(long_path)
        assert "exceeds maximum length" in str(exc_info.value)

    def test_home_expansion(self):
        """Test tilde expansion."""
        with patch.dict(os.environ, {"HOME": "/home/user"}):
            result = normalize_path("~/test")
            assert result == "/home/user/test"

    def test_normalize_dots(self):
        """Test . and .. normalization."""
        # Use absolute paths to avoid issues with current directory
        result = normalize_path("/home/user/../test")
        assert result == "/home/test"

    def test_normalize_slashes(self):
        """Test duplicate slash removal."""
        result = normalize_path("/home//user///test/")
        assert "//" not in result
        assert "///" not in result

    def test_invalid_path(self):
        """Invalid path should raise error."""
        with patch("pathlib.Path.resolve", side_effect=OSError("Invalid")):
            with pytest.raises(PathError) as exc_info:
                normalize_path("/invalid\0path")
            assert "Invalid path" in str(exc_info.value)


class TestIsSafePath:
    """Test safe path checking."""

    def test_safe_path_within_base(self):
        """Path within base should be safe."""
        assert is_safe_path("/home/user", "test.txt")
        assert is_safe_path("/home/user", "subdir/test.txt")

    def test_unsafe_path_traversal(self):
        """Path traversal should be unsafe."""
        assert not is_safe_path("/home/user", "../etc/passwd")
        assert not is_safe_path("/home/user", "../../root")

    def test_safe_path_at_base(self):
        """Path at base should be safe."""
        assert is_safe_path("/home/user", ".")
        assert is_safe_path("/home/user", "")

    def test_symlink_handling(self):
        """Test symlink following option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            safe_file = base / "safe.txt"
            safe_file.touch()

            # Test without following symlinks
            assert is_safe_path(str(base), "safe.txt", follow_symlinks=False)

            # Test with following symlinks
            link = base / "link.txt"
            link.symlink_to(safe_file)
            assert is_safe_path(str(base), "link.txt", follow_symlinks=True)

    def test_invalid_base(self):
        """Invalid base should return False."""
        with patch("shadowfs.foundation.path_utils.normalize_path", side_effect=PathError("Invalid")):
            assert not is_safe_path("/invalid", "test.txt")


class TestJoinPaths:
    """Test path joining."""

    def test_join_multiple_paths(self):
        """Test joining multiple path components."""
        result = join_paths("/home", "user", "test.txt")
        assert result.endswith("user/test.txt")

    def test_join_empty_components(self):
        """Empty components should be filtered."""
        result = join_paths("/home", "", "user", "", "test.txt")
        assert result.endswith("user/test.txt")

    def test_join_no_paths(self):
        """No paths should raise error."""
        with pytest.raises(PathError) as exc_info:
            join_paths()
        assert "No paths provided" in str(exc_info.value)

    def test_join_all_empty(self):
        """All empty paths should raise error."""
        with pytest.raises(PathError) as exc_info:
            join_paths("", "", "")
        assert "All paths are empty" in str(exc_info.value)

    def test_join_error_handling(self):
        """Join errors should be wrapped."""
        with patch("os.path.join", side_effect=OSError("Join failed")):
            with pytest.raises(PathError) as exc_info:
                join_paths("/home", "user")
            assert "Failed to join paths" in str(exc_info.value)


class TestSplitPath:
    """Test path splitting."""

    def test_split_normal_path(self):
        """Test splitting normal path."""
        dir_part, file_part = split_path("/home/user/test.txt")
        assert dir_part == "/home/user"
        assert file_part == "test.txt"

    def test_split_empty_path(self):
        """Empty path should raise error."""
        with pytest.raises(PathError) as exc_info:
            split_path("")
        assert "Path cannot be empty" in str(exc_info.value)

    def test_split_virtual_path(self):
        """Virtual paths should split without normalization."""
        with patch("shadowfs.foundation.path_utils.normalize_path", side_effect=PathError("Virtual")):
            dir_part, file_part = split_path("virtual/path.txt")
            assert dir_part == "virtual"
            assert file_part == "path.txt"


class TestGetParentPath:
    """Test parent path extraction."""

    def test_get_parent_normal(self):
        """Test getting parent of normal path."""
        parent = get_parent_path("/home/user/test.txt")
        assert parent == "/home/user"

    def test_get_parent_empty(self):
        """Empty path should raise error."""
        with pytest.raises(PathError) as exc_info:
            get_parent_path("")
        assert "Path cannot be empty" in str(exc_info.value)

    def test_get_parent_no_parent(self):
        """Root path has no parent."""
        with pytest.raises(PathError) as exc_info:
            get_parent_path("/")
        assert "Path has no parent" in str(exc_info.value)


class TestGetFilename:
    """Test filename extraction."""

    def test_get_filename_normal(self):
        """Test extracting filename from path."""
        filename = get_filename("/home/user/test.txt")
        assert filename == "test.txt"

    def test_get_filename_empty(self):
        """Empty path should raise error."""
        with pytest.raises(PathError) as exc_info:
            get_filename("")
        assert "Path cannot be empty" in str(exc_info.value)

    def test_filename_too_long(self):
        """Filename exceeding limit should raise error."""
        long_name = "a" * (Limits.MAX_FILENAME_LENGTH + 1)
        with pytest.raises(PathError) as exc_info:
            get_filename(f"/home/{long_name}")
        assert "exceeds maximum length" in str(exc_info.value)


class TestGetExtension:
    """Test file extension extraction."""

    def test_get_extension_normal(self):
        """Test extracting extension."""
        assert get_extension("/home/user/test.txt") == ".txt"
        assert get_extension("file.tar.gz") == ".gz"

    def test_get_extension_no_extension(self):
        """File without extension."""
        assert get_extension("/home/user/README") == ""

    def test_get_extension_hidden_file(self):
        """Hidden file with extension."""
        assert get_extension(".bashrc") == ""
        assert get_extension(".gitignore.bak") == ".bak"


class TestResolveSymlinks:
    """Test symbolic link resolution."""

    def test_resolve_normal_path(self):
        """Non-symlink path should resolve to itself."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.touch()
            resolved = resolve_symlinks(str(test_file))
            assert Path(resolved).exists()

    def test_resolve_empty_path(self):
        """Empty path should raise error."""
        with pytest.raises(PathError) as exc_info:
            resolve_symlinks("")
        assert "Path cannot be empty" in str(exc_info.value)

    def test_resolve_max_depth(self):
        """Exceeding max depth should raise error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create chain of symlinks
            for i in range(5):
                link = base / f"link{i}"
                target = base / f"link{i+1}"
                link.symlink_to(target)

            # Final target
            (base / "link5").touch()

            # Should work with sufficient depth
            resolve_symlinks(str(base / "link0"), max_depth=10)

            # Should fail with insufficient depth
            with pytest.raises(PathError) as exc_info:
                resolve_symlinks(str(base / "link0"), max_depth=2)
            assert "Symlink depth exceeds" in str(exc_info.value)

    def test_circular_symlink(self):
        """Circular symlinks should be detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            link1 = base / "link1"
            link2 = base / "link2"

            link1.symlink_to(link2)
            link2.symlink_to(link1)

            with pytest.raises(PathError) as exc_info:
                resolve_symlinks(str(link1))
            assert "Circular symlink" in str(exc_info.value)

    def test_resolve_failure(self):
        """Resolution failure should raise error."""
        with patch("os.path.islink", side_effect=OSError("Failed")):
            with pytest.raises(PathError) as exc_info:
                resolve_symlinks("/some/path")
            assert "Failed to resolve" in str(exc_info.value)

    def test_resolve_relative_symlink(self):
        """Test resolving relative symlinks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            subdir = base / "subdir"
            subdir.mkdir()

            # Create target file
            target = subdir / "target.txt"
            target.touch()

            # Create relative symlink
            link = base / "link.txt"
            link.symlink_to("subdir/target.txt")  # Relative link

            # Should resolve correctly
            resolved = resolve_symlinks(str(link))
            assert Path(resolved).exists()
            assert resolved.endswith("target.txt")


class TestValidateFilename:
    """Test filename validation."""

    def test_valid_filenames(self):
        """Test valid filenames."""
        assert validate_filename("test.txt")
        assert validate_filename("file-name_123.tar.gz")
        assert validate_filename("README")

    def test_empty_filename(self):
        """Empty filename is invalid."""
        assert not validate_filename("")

    def test_filename_too_long(self):
        """Filename exceeding limit is invalid."""
        long_name = "a" * (Limits.MAX_FILENAME_LENGTH + 1)
        assert not validate_filename(long_name)

    def test_filename_with_separator(self):
        """Filename with path separator is invalid."""
        assert not validate_filename("dir/file.txt")
        assert not validate_filename("dir\\file.txt")

    def test_filename_with_null(self):
        """Filename with null byte is invalid."""
        assert not validate_filename("file\0.txt")

    def test_reserved_names(self):
        """Reserved names are invalid."""
        assert not validate_filename(".")
        assert not validate_filename("..")

    def test_control_characters(self):
        """Filenames with control characters are invalid."""
        assert not validate_filename("file\x01.txt")
        assert not validate_filename("file\n.txt")


class TestIsAbsolutePath:
    """Test absolute path checking."""

    def test_absolute_paths(self):
        """Test absolute path detection."""
        assert is_absolute_path("/home/user")
        assert is_absolute_path("/")

    def test_relative_paths(self):
        """Test relative path detection."""
        assert not is_absolute_path("home/user")
        assert not is_absolute_path("./test")
        assert not is_absolute_path("../test")

    def test_empty_path(self):
        """Empty path is not absolute."""
        assert not is_absolute_path("")


class TestMakeRelative:
    """Test making paths relative."""

    def test_make_relative_normal(self):
        """Test making path relative to base."""
        relative = make_relative("/home/user", "/home/user/docs/test.txt")
        assert relative == "docs/test.txt"

    def test_make_relative_same(self):
        """Path same as base should return '.'."""
        relative = make_relative("/home/user", "/home/user")
        assert relative == "."

    def test_make_relative_empty(self):
        """Empty paths should raise error."""
        with pytest.raises(PathError) as exc_info:
            make_relative("", "/home/user")
        assert "cannot be empty" in str(exc_info.value)

        with pytest.raises(PathError):
            make_relative("/home", "")

    def test_make_relative_not_within(self):
        """Path not within base should raise error."""
        with pytest.raises(PathError) as exc_info:
            make_relative("/home/user", "/etc/passwd")
        assert "not within base" in str(exc_info.value)

    def test_make_relative_error(self):
        """OS errors should be wrapped."""
        with patch("os.path.relpath", side_effect=ValueError("Invalid")):
            with pytest.raises(PathError) as exc_info:
                make_relative("/home", "/home/test")
            assert "Failed to make relative" in str(exc_info.value)


class TestParseVirtualPath:
    """Test virtual path parsing."""

    def test_parse_virtual_with_layer(self):
        """Test parsing virtual path with layer."""
        layer, path = parse_virtual_path("/by-type/python/test.py")
        assert layer == "by-type"
        assert path == "python/test.py"

    def test_parse_virtual_layer_only(self):
        """Test parsing with layer name only."""
        layer, path = parse_virtual_path("by-type")
        assert layer == "by-type"
        assert path == ""

    def test_parse_empty(self):
        """Empty path should return None, empty."""
        layer, path = parse_virtual_path("")
        assert layer is None
        assert path == ""

    def test_parse_windows_slashes(self):
        """Windows slashes should be normalized."""
        layer, path = parse_virtual_path("by-type\\python\\test.py")
        assert layer == "by-type"
        assert path == "python/test.py"

    def test_parse_no_leading_slash(self):
        """Path without leading slash."""
        layer, path = parse_virtual_path("by-type/test.py")
        assert layer == "by-type"
        assert path == "test.py"

    def test_cache_behavior(self):
        """Test that results are cached."""
        # Clear cache first
        parse_virtual_path.cache_clear()

        # First call
        result1 = parse_virtual_path("/by-type/test.py")

        # Check cache info shows 1 miss
        info = parse_virtual_path.cache_info()
        assert info.misses == 1
        assert info.hits == 0

        # Second call with same input
        result2 = parse_virtual_path("/by-type/test.py")
        assert result1 == result2

        # Check cache info shows 1 hit
        info = parse_virtual_path.cache_info()
        assert info.hits == 1


class TestIsHiddenFile:
    """Test hidden file detection."""

    def test_hidden_files(self):
        """Test hidden file detection."""
        assert is_hidden_file(".bashrc")
        assert is_hidden_file("/home/user/.config")
        assert is_hidden_file(".gitignore")

    def test_not_hidden(self):
        """Normal files are not hidden."""
        assert not is_hidden_file("test.txt")
        assert not is_hidden_file("/home/user/file")

    def test_special_dirs(self):
        """Special directories . and .. are not hidden."""
        assert not is_hidden_file(".")
        assert not is_hidden_file("..")
        assert not is_hidden_file("/path/to/.")


class TestListPathComponents:
    """Test path component listing."""

    def test_list_components_absolute(self):
        """Test listing components of absolute path."""
        components = list_path_components("/home/user/test.txt")
        assert "/" in components or components[0].endswith(":")  # Windows
        assert "home" in components
        assert "user" in components
        assert "test.txt" in components

    def test_list_components_empty(self):
        """Empty path should return empty list."""
        assert list_path_components("") == []

    def test_list_components_relative(self):
        """Test listing components of relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            components = list_path_components("subdir/file.txt")
            assert "subdir" in components
            assert "file.txt" in components


class TestCommonPathPrefix:
    """Test common path prefix finding."""

    def test_common_prefix_normal(self):
        """Test finding common prefix."""
        paths = [
            "/home/user/docs/file1.txt",
            "/home/user/docs/file2.txt",
            "/home/user/docs/subdir/file3.txt"
        ]
        prefix = common_path_prefix(paths)
        assert prefix.endswith("docs")

    def test_common_prefix_empty(self):
        """Empty list should return empty string."""
        assert common_path_prefix([]) == ""

    def test_common_prefix_single(self):
        """Single path should return itself."""
        assert common_path_prefix(["/home/user"]) == "/home/user"

    def test_common_prefix_no_common(self):
        """No common prefix should return empty or root."""
        paths = ["/home/user", "/etc/config"]
        prefix = common_path_prefix(paths)
        # On Unix, this would be "/"
        assert prefix in ("", "/")

    def test_common_prefix_error(self):
        """Errors should return empty string or single path."""
        with patch("shadowfs.foundation.path_utils.normalize_path", side_effect=PathError("Invalid")):
            # When normalization fails, it returns the input path
            result = common_path_prefix(["/invalid"])
            # May return empty or the path itself depending on the error
            assert result in ("", "/invalid")

    def test_common_prefix_fallback(self):
        """Test fallback to commonprefix for older Python."""
        # Temporarily remove commonpath to test fallback
        original_commonpath = getattr(os.path, 'commonpath', None)
        if hasattr(os.path, 'commonpath'):
            delattr(os.path, 'commonpath')

        try:
            paths = ["/home/user/file1", "/home/user/file2"]
            result = common_path_prefix(paths)
            assert "/home/user" in result
        finally:
            # Restore commonpath
            if original_commonpath:
                os.path.commonpath = original_commonpath

    def test_common_prefix_exception(self):
        """Test exception handling in common_path_prefix."""
        # Test ValueError exception from commonpath
        with patch("os.path.commonpath", side_effect=ValueError("No common path")):
            result = common_path_prefix(["/home/user", "/etc/config"])
            assert result == ""


class TestTrailingSlash:
    """Test trailing slash operations."""

    def test_ensure_trailing_slash(self):
        """Test ensuring trailing slash."""
        assert ensure_trailing_slash("/home/user") == f"/home/user{os.sep}"

        # Test path that already has trailing slash
        path_with_slash = f"/home/user{os.sep}"
        assert ensure_trailing_slash(path_with_slash) == path_with_slash

    def test_ensure_trailing_empty(self):
        """Empty path should return separator."""
        assert ensure_trailing_slash("") == os.sep

    def test_remove_trailing_slash(self):
        """Test removing trailing slash."""
        assert remove_trailing_slash("/home/user/") == "/home/user"
        assert remove_trailing_slash("/home/user") == "/home/user"

        # Test multiple trailing slashes
        assert remove_trailing_slash("/home/user///") == "/home/user"

    def test_remove_trailing_root(self):
        """Root path should remain unchanged."""
        assert remove_trailing_slash("/") == "/"
        assert remove_trailing_slash(os.sep) == os.sep

    def test_remove_trailing_empty(self):
        """Empty path should remain empty."""
        assert remove_trailing_slash("") == ""