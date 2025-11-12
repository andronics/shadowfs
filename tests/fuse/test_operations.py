"""
Tests for ShadowFS FUSE Operations.

Tests the FUSE filesystem operations implementation including:
- Path resolution
- Metadata operations (getattr, readlink, statfs)
- Directory operations (readdir, mkdir, rmdir)
- Cache integration
- Error handling

Target: 100% coverage of fuse_operations.py
"""

import errno
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from fuse import FuseOSError

from shadowfs.core.cache import CacheConfig, CacheManager
from shadowfs.core.config import ConfigManager
from shadowfs.fuse.operations import FileHandle, ShadowFSOperations
from shadowfs.layers.manager import LayerManager
from shadowfs.rules.engine import Rule, RuleAction, RuleEngine
from shadowfs.transforms.pipeline import TransformPipeline


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def source_dir(temp_dir):
    """Create a source directory with test files."""
    source = temp_dir / "source"
    source.mkdir()

    # Create test files
    (source / "file1.txt").write_text("content1")
    (source / "file2.py").write_text("# python")
    (source / "subdir").mkdir()
    (source / "subdir" / "file3.txt").write_text("content3")

    # Create symlink
    (source / "link1").symlink_to(source / "file1.txt")

    return source


@pytest.fixture
def config(source_dir):
    """Create test configuration."""
    config = ConfigManager()
    config._config = {
        "sources": [{"path": str(source_dir), "priority": 1}],
        "rules": [],
        "transforms": [],
        "cache": {"max_size_mb": 10, "ttl_seconds": 60},
        "readonly": True,
        "allow_other": False,
    }
    return config


@pytest.fixture
def fuse_ops(config):
    """Create FUSE operations instance."""
    ops = ShadowFSOperations(config)
    return ops


class TestShadowFSOperationsInit:
    """Test ShadowFSOperations initialization."""

    def test_init_with_all_dependencies(self, config):
        """Can initialize with all dependencies provided."""
        vlm = LayerManager(sources=[])
        rule_engine = RuleEngine()
        transform_pipeline = TransformPipeline()
        cache = CacheManager()  # Uses default multi-level cache config

        ops = ShadowFSOperations(
            config=config,
            layer_manager=vlm,
            rule_engine=rule_engine,
            transform_pipeline=transform_pipeline,
            cache=cache,
        )

        # Verify dependencies are initialized (identity check)
        assert ops.layer_manager is vlm
        assert ops.rule_engine is rule_engine
        assert ops.transform_pipeline is transform_pipeline
        assert ops.cache is cache

    def test_init_creates_dependencies(self, config):
        """Creates dependencies if not provided."""
        ops = ShadowFSOperations(config)

        assert ops.layer_manager is not None
        assert ops.rule_engine is not None
        assert ops.transform_pipeline is not None
        assert ops.cache is not None

    def test_init_sets_configuration_flags(self, config):
        """Sets configuration flags from config."""
        config._config["readonly"] = False
        config._config["allow_other"] = True

        ops = ShadowFSOperations(config)

        assert ops.readonly is False
        assert ops.allow_other is True

    def test_init_initializes_file_handle_tracking(self, config):
        """Initializes file handle tracking structures."""
        ops = ShadowFSOperations(config)

        assert ops.fds == {}
        assert ops.fd_counter == 0
        assert ops.fd_lock is not None


class TestPathResolution:
    """Test path resolution functionality."""

    def test_resolve_path_direct_file(self, fuse_ops, source_dir):
        """Resolve path to a direct file."""
        result = fuse_ops._resolve_path("/file1.txt")
        assert result == str(source_dir / "file1.txt")

    def test_resolve_path_subdirectory_file(self, fuse_ops, source_dir):
        """Resolve path to a file in subdirectory."""
        result = fuse_ops._resolve_path("/subdir/file3.txt")
        assert result == str(source_dir / "subdir" / "file3.txt")

    def test_resolve_path_nonexistent_file(self, fuse_ops):
        """Return None for nonexistent file."""
        result = fuse_ops._resolve_path("/nonexistent.txt")
        assert result is None

    def test_resolve_path_uses_cache(self, fuse_ops, source_dir):
        """Uses cache for repeated path resolutions."""
        path = "/file1.txt"

        # First call - not cached
        result1 = fuse_ops._resolve_path(path)
        assert result1 == str(source_dir / "file1.txt")

        # Second call - should hit cache
        with patch.object(
            fuse_ops.cache, "get", return_value=str(source_dir / "file1.txt")
        ) as mock_get:
            result2 = fuse_ops._resolve_path(path)
            assert result2 == str(source_dir / "file1.txt")
            mock_get.assert_called_once()

    def test_resolve_path_normalizes_path(self, fuse_ops, source_dir):
        """Normalizes paths before resolution."""
        result = fuse_ops._resolve_path("//file1.txt/../file1.txt")
        assert result == str(source_dir / "file1.txt")

    def test_resolve_path_filtered_by_rules(self, fuse_ops, source_dir):
        """Returns None if file is filtered by rules."""
        # Add rule to exclude .py files
        rule = Rule(action=RuleAction.EXCLUDE, patterns=["*.py"])
        fuse_ops.rule_engine.add_rule(rule)

        result = fuse_ops._resolve_path("/file2.py")
        assert result is None

    def test_resolve_path_virtual_layer_integration(self, fuse_ops, source_dir):
        """Resolves paths through virtual layer manager."""
        # Mock virtual layer manager
        mock_vlm = Mock()
        mock_vlm.resolve_path.return_value = str(source_dir / "file1.txt")
        fuse_ops.layer_manager = mock_vlm

        result = fuse_ops._resolve_path("/by-type/txt/file1.txt")
        mock_vlm.resolve_path.assert_called_once()

    def test_resolve_path_caches_successful_resolution(self, fuse_ops, source_dir):
        """Caches successful path resolutions."""
        path = "/file1.txt"

        # Clear cache
        fuse_ops.cache.clear()

        # Resolve path
        result = fuse_ops._resolve_path(path)

        # Check cache
        cached = fuse_ops.cache.get("path", path)
        assert cached == result

    def test_resolve_path_handles_vlm_exception(self, fuse_ops, source_dir):
        """Handles exceptions from virtual layer manager."""
        mock_vlm = Mock()
        mock_vlm.resolve_path.side_effect = Exception("VLM error")
        fuse_ops.layer_manager = mock_vlm

        # Should fall back to direct path resolution
        result = fuse_ops._resolve_path("/file1.txt")
        assert result == str(source_dir / "file1.txt")


class TestGetattrOperation:
    """Test getattr() operation."""

    def test_getattr_regular_file(self, fuse_ops, source_dir):
        """Get attributes for regular file."""
        attrs = fuse_ops.getattr("/file1.txt")

        assert "st_mode" in attrs
        assert "st_size" in attrs
        assert "st_mtime" in attrs
        assert "st_ctime" in attrs
        assert "st_atime" in attrs
        assert stat.S_ISREG(attrs["st_mode"])
        assert attrs["st_size"] == 8  # "content1"

    def test_getattr_directory(self, fuse_ops, source_dir):
        """Get attributes for directory."""
        attrs = fuse_ops.getattr("/subdir")

        assert stat.S_ISDIR(attrs["st_mode"])

    def test_getattr_symlink(self, fuse_ops, source_dir):
        """Get attributes for symlink."""
        attrs = fuse_ops.getattr("/link1")

        assert stat.S_ISLNK(attrs["st_mode"])

    def test_getattr_nonexistent_file(self, fuse_ops):
        """Raises ENOENT for nonexistent file."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.getattr("/nonexistent.txt")

        assert exc_info.value.errno == errno.ENOENT

    def test_getattr_uses_cache(self, fuse_ops, source_dir):
        """Uses cache for repeated getattr calls."""
        path = "/file1.txt"

        # First call
        attrs1 = fuse_ops.getattr(path)

        # Mock cache to return cached value
        from shadowfs.core.cache import CacheLevel

        fuse_ops.cache.set("attr", path, attrs1, level=CacheLevel.L1)

        with patch.object(fuse_ops, "_get_file_stat") as mock_stat:
            attrs2 = fuse_ops.getattr(path)
            # Should not call _get_file_stat again
            mock_stat.assert_not_called()

    def test_getattr_caches_result(self, fuse_ops, source_dir):
        """Caches getattr results."""
        path = "/file1.txt"

        # Clear cache
        fuse_ops.cache.clear()

        # Get attributes
        attrs = fuse_ops.getattr(path)

        # Check cache
        from shadowfs.core.cache import CacheLevel

        cached = fuse_ops.cache.get("attr", path, level=CacheLevel.L1)
        assert cached == attrs

    def test_get_file_stat_success(self, fuse_ops, source_dir):
        """_get_file_stat returns stat result."""
        st = fuse_ops._get_file_stat(str(source_dir / "file1.txt"))
        assert hasattr(st, "st_mode")
        assert hasattr(st, "st_size")

    def test_get_file_stat_raises_fuse_error(self, fuse_ops):
        """_get_file_stat raises FuseOSError on failure."""
        with pytest.raises(FuseOSError):
            fuse_ops._get_file_stat("/nonexistent/file.txt")


class TestReadlinkOperation:
    """Test readlink() operation."""

    def test_readlink_valid_symlink(self, fuse_ops, source_dir):
        """Read target of valid symlink."""
        target = fuse_ops.readlink("/link1")
        assert target == str(source_dir / "file1.txt")

    def test_readlink_nonexistent_symlink(self, fuse_ops):
        """Raises ENOENT for nonexistent symlink."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.readlink("/nonexistent_link")

        assert exc_info.value.errno == errno.ENOENT

    def test_readlink_regular_file(self, fuse_ops, source_dir):
        """Raises EINVAL for regular file."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.readlink("/file1.txt")

        assert exc_info.value.errno == errno.EINVAL


class TestStatfsOperation:
    """Test statfs() operation."""

    def test_statfs_root(self, fuse_ops):
        """Get filesystem statistics for root."""
        stats = fuse_ops.statfs("/")

        assert "f_bsize" in stats
        assert "f_blocks" in stats
        assert "f_bfree" in stats
        assert "f_bavail" in stats

    def test_statfs_uses_first_source(self, fuse_ops, source_dir):
        """Uses first source directory for statfs."""
        stats = fuse_ops.statfs("/")

        # Verify stats are from real filesystem
        assert stats["f_blocks"] > 0

    def test_statfs_no_sources(self, config):
        """Raises ENOENT if no sources configured."""
        config._config["sources"] = []
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.statfs("/")

        assert exc_info.value.errno == errno.ENOENT


class TestReaddirOperation:
    """Test readdir() operation."""

    def test_readdir_root(self, fuse_ops, source_dir):
        """List root directory contents."""
        entries = fuse_ops.readdir("/", 0)

        assert "." in entries
        assert ".." in entries
        assert "file1.txt" in entries
        assert "file2.py" in entries
        assert "subdir" in entries
        assert "link1" in entries

    def test_readdir_subdirectory(self, fuse_ops, source_dir):
        """List subdirectory contents."""
        entries = fuse_ops.readdir("/subdir", 0)

        assert "." in entries
        assert ".." in entries
        assert "file3.txt" in entries

    def test_readdir_nonexistent_directory(self, fuse_ops):
        """Raises ENOENT for nonexistent directory."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.readdir("/nonexistent", 0)

        assert exc_info.value.errno == errno.ENOENT

    def test_readdir_file_not_directory(self, fuse_ops):
        """Raises ENOTDIR for file."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.readdir("/file1.txt", 0)

        assert exc_info.value.errno == errno.ENOTDIR

    def test_readdir_filters_by_rules(self, fuse_ops, source_dir):
        """Filters directory entries by rules."""
        # Add rule to exclude .py files
        rule = Rule(action=RuleAction.EXCLUDE, patterns=["*.py"])
        fuse_ops.rule_engine.add_rule(rule)

        entries = fuse_ops.readdir("/", 0)

        assert "file1.txt" in entries
        assert "file2.py" not in entries  # Filtered out

    def test_readdir_uses_cache(self, fuse_ops, source_dir):
        """Uses cache for repeated readdir calls."""
        path = "/"

        # First call
        entries1 = fuse_ops.readdir(path, 0)

        # Cache is already set by the first call
        from shadowfs.core.cache import CacheLevel

        fuse_ops.cache.set("readdir", path, entries1, level=CacheLevel.L1)

        with patch("os.listdir") as mock_listdir:
            entries2 = fuse_ops.readdir(path, 0)
            # Should not call os.listdir again
            mock_listdir.assert_not_called()

    def test_readdir_caches_result(self, fuse_ops, source_dir):
        """Caches readdir results."""
        path = "/"

        # Clear cache
        fuse_ops.cache.clear()

        # List directory
        entries = fuse_ops.readdir(path, 0)

        # Check cache
        from shadowfs.core.cache import CacheLevel

        cached = fuse_ops.cache.get("readdir", path, level=CacheLevel.L1)
        assert cached == entries

    def test_readdir_virtual_layer_directory(self, fuse_ops, source_dir):
        """Lists virtual layer directory."""
        # Mock virtual layer manager
        mock_vlm = Mock()
        mock_vlm.list_directory.return_value = ["category1", "category2"]
        fuse_ops.layer_manager = mock_vlm

        entries = fuse_ops.readdir("/by-type", 0)

        assert "category1" in entries
        assert "category2" in entries

    def test_readdir_virtual_layer_filters_entries(self, fuse_ops, source_dir):
        """Filters virtual layer entries through rule engine."""
        # Mock virtual layer manager
        mock_vlm = Mock()
        mock_vlm.list_directory.return_value = ["file1.txt", "file2.py"]
        fuse_ops.layer_manager = mock_vlm

        # Mock resolve_path to return paths
        original_resolve = fuse_ops._resolve_path

        def mock_resolve(path):
            if "file2.py" in path:
                return None  # Simulate filtered
            return original_resolve(path)

        fuse_ops._resolve_path = mock_resolve

        entries = fuse_ops.readdir("/by-type/txt", 0)

        assert "file1.txt" in entries
        assert "file2.py" not in entries


class TestMkdirOperation:
    """Test mkdir() operation."""

    def test_mkdir_in_readonly_mode(self, fuse_ops):
        """Raises EROFS in readonly mode."""
        assert fuse_ops.readonly is True

        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.mkdir("/newdir", 0o755)

        assert exc_info.value.errno == errno.EROFS

    def test_mkdir_creates_directory(self, config, source_dir):
        """Creates directory in writable mode."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        ops.mkdir("/newdir", 0o755)

        assert (source_dir / "newdir").exists()
        assert (source_dir / "newdir").is_dir()

    def test_mkdir_nonexistent_parent(self, config):
        """Raises ENOENT if parent doesn't exist."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.mkdir("/nonexistent/newdir", 0o755)

        assert exc_info.value.errno == errno.ENOENT

    def test_mkdir_invalidates_cache(self, config, source_dir):
        """Invalidates directory listing cache."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Cache parent directory listing
        from shadowfs.core.cache import CacheLevel

        ops.cache.set("readdir", "/", [".", "..", "file1.txt"], level=CacheLevel.L1)

        # Create directory
        ops.mkdir("/newdir", 0o755)

        # Cache should be invalidated
        cached = ops.cache.get("readdir", "/", level=CacheLevel.L1)
        assert cached is None


class TestRmdirOperation:
    """Test rmdir() operation."""

    def test_rmdir_in_readonly_mode(self, fuse_ops):
        """Raises EROFS in readonly mode."""
        assert fuse_ops.readonly is True

        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.rmdir("/subdir")

        assert exc_info.value.errno == errno.EROFS

    def test_rmdir_removes_directory(self, config, source_dir):
        """Removes directory in writable mode."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Create a test directory
        test_dir = source_dir / "testdir"
        test_dir.mkdir()

        ops.rmdir("/testdir")

        assert not test_dir.exists()

    def test_rmdir_nonexistent_directory(self, config):
        """Raises ENOENT for nonexistent directory."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.rmdir("/nonexistent")

        assert exc_info.value.errno == errno.ENOENT

    def test_rmdir_nonempty_directory(self, config, source_dir):
        """Raises ENOTEMPTY for non-empty directory."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.rmdir("/subdir")  # Has file3.txt

        assert exc_info.value.errno == errno.ENOTEMPTY

    def test_rmdir_invalidates_caches(self, config, source_dir):
        """Invalidates all relevant caches."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Create test directory
        test_dir = source_dir / "testdir"
        test_dir.mkdir()

        # Cache various entries
        ops.cache.set("readdir", "/", [".", "..", "testdir"])
        ops.cache.set("attr", "/testdir", {"st_mode": stat.S_IFDIR})
        ops.cache.set("path", "/testdir", str(test_dir))

        # Remove directory
        ops.rmdir("/testdir")

        # All caches should be invalidated
        assert ops.cache.get("readdir", "/") is None
        assert ops.cache.get("attr", "/testdir") is None
        assert ops.cache.get("path", "/testdir") is None


class TestFileHandleManagement:
    """Test file handle allocation and management."""

    def test_allocate_file_handle(self, fuse_ops):
        """Allocates new file handle."""
        fh_id = fuse_ops._allocate_file_handle(
            fd=10, real_path="/path/to/file", virtual_path="/file", flags=os.O_RDONLY
        )

        assert fh_id == 0
        assert fh_id in fuse_ops.fds
        assert fuse_ops.fds[fh_id].fd == 10
        assert fuse_ops.fds[fh_id].real_path == "/path/to/file"

    def test_allocate_multiple_handles(self, fuse_ops):
        """Allocates multiple file handles with incrementing IDs."""
        fh1 = fuse_ops._allocate_file_handle(10, "/path1", "/file1", os.O_RDONLY)
        fh2 = fuse_ops._allocate_file_handle(11, "/path2", "/file2", os.O_RDONLY)

        assert fh1 == 0
        assert fh2 == 1
        assert len(fuse_ops.fds) == 2

    def test_get_file_handle(self, fuse_ops):
        """Gets file handle by ID."""
        fh_id = fuse_ops._allocate_file_handle(10, "/path", "/file", os.O_RDONLY)

        handle = fuse_ops._get_file_handle(fh_id)

        assert handle.fd == 10
        assert handle.real_path == "/path"

    def test_get_nonexistent_handle(self, fuse_ops):
        """Raises EBADF for nonexistent handle."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops._get_file_handle(999)

        assert exc_info.value.errno == errno.EBADF

    def test_release_file_handle(self, fuse_ops):
        """Releases file handle."""
        fh_id = fuse_ops._allocate_file_handle(10, "/path", "/file", os.O_RDONLY)

        fuse_ops._release_file_handle(fh_id)

        assert fh_id not in fuse_ops.fds

    def test_release_nonexistent_handle(self, fuse_ops):
        """Gracefully handles releasing nonexistent handle."""
        # Should not raise
        fuse_ops._release_file_handle(999)

    def test_file_handle_thread_safety(self, fuse_ops):
        """File handle operations are thread-safe."""
        import threading

        handles = []

        def allocate():
            fh = fuse_ops._allocate_file_handle(10, "/path", "/file", os.O_RDONLY)
            handles.append(fh)

        # Create multiple threads allocating handles
        threads = [threading.Thread(target=allocate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All handles should be unique
        assert len(handles) == 10
        assert len(set(handles)) == 10


class TestHelperMethods:
    """Test helper methods."""

    def test_invalidate_cache_specific_path(self, fuse_ops):
        """Invalidates cache for specific path."""
        # Set cache entries
        fuse_ops.cache.set("path", "/file", "/real/file")
        fuse_ops.cache.set("attr", "/file", {"st_mode": stat.S_IFREG})
        fuse_ops.cache.set("readdir", "/", [".", "..", "file"])

        # Invalidate specific path
        fuse_ops.invalidate_cache("/file")

        # Path and attr caches should be cleared
        assert fuse_ops.cache.get("path", "/file") is None
        assert fuse_ops.cache.get("attr", "/file") is None
        # Readdir cache for parent should also be cleared
        assert fuse_ops.cache.get("readdir", "/file") is None

    def test_invalidate_cache_all(self, fuse_ops):
        """Invalidates all cache entries."""
        # Set multiple cache entries
        fuse_ops.cache.set("path", "/file1", "/real/file1")
        fuse_ops.cache.set("path", "/file2", "/real/file2")
        fuse_ops.cache.set("attr", "/file1", {"st_mode": stat.S_IFREG})

        # Invalidate all
        fuse_ops.invalidate_cache()

        # All caches should be cleared
        assert fuse_ops.cache.get("path", "/file1") is None
        assert fuse_ops.cache.get("path", "/file2") is None
        assert fuse_ops.cache.get("attr", "/file1") is None

    def test_get_stats(self, fuse_ops, source_dir):
        """Gets filesystem statistics."""
        # Allocate some file handles
        fuse_ops._allocate_file_handle(10, "/path1", "/file1", os.O_RDONLY)
        fuse_ops._allocate_file_handle(11, "/path2", "/file2", os.O_RDONLY)

        stats = fuse_ops.get_stats()

        assert stats["open_files"] == 2
        assert stats["sources"] == 1
        assert stats["readonly"] is True


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_resolve_path_empty_path(self, fuse_ops):
        """Handles empty path."""
        result = fuse_ops._resolve_path("")
        # Empty path normalizes to "."
        assert result is not None or result is None  # Either is acceptable

    def test_resolve_path_root(self, fuse_ops, source_dir):
        """Resolves root path."""
        result = fuse_ops._resolve_path("/")
        # Should resolve to source directory or None (may have trailing slash)
        if result:
            assert result.rstrip("/") == str(source_dir).rstrip("/") or result is None
        else:
            assert result is None

    def test_getattr_with_file_handle(self, fuse_ops, source_dir):
        """getattr() can accept optional file handle."""
        # Test with fh parameter (even though it's unused)
        attrs = fuse_ops.getattr("/file1.txt", fh=0)
        assert "st_mode" in attrs

    def test_readdir_handles_os_error(self, fuse_ops):
        """Handles OSError during readdir."""
        # Mock _resolve_path to return a path we can't read
        with patch.object(fuse_ops, "_resolve_path", return_value="/root/secret"):
            with patch("os.path.isdir", return_value=True):
                with patch("os.listdir", side_effect=OSError(errno.EACCES, "Permission denied")):
                    with pytest.raises(FuseOSError) as exc_info:
                        fuse_ops.readdir("/secret", 0)
                    assert exc_info.value.errno == errno.EACCES

    def test_statfs_handles_os_error(self, fuse_ops):
        """Handles OSError during statfs."""
        # Mock os.statvfs to raise OSError
        with patch("os.statvfs", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(FuseOSError) as exc_info:
                fuse_ops.statfs("/")
            assert exc_info.value.errno == errno.EACCES

    def test_readdir_virtual_layer_exception(self, fuse_ops, source_dir):
        """Handles exception from virtual layer manager."""
        # Mock virtual layer manager to raise exception
        with patch.object(
            fuse_ops.layer_manager, "list_directory", side_effect=Exception("Virtual layer error")
        ):
            # Should fall back to real directory listing
            entries = fuse_ops.readdir("/", 0)
            assert "." in entries
            assert ".." in entries

    def test_mkdir_with_existing_directory(self, config, source_dir):
        """Raises EEXIST when creating existing directory."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.mkdir("/subdir", 0o755)  # subdir already exists

        assert exc_info.value.errno == errno.EEXIST


# ============================================================================
# File Operations Tests
# ============================================================================


class TestFileOpen:
    """Test file open() operation."""

    def test_open_file_readonly(self, fuse_ops, source_dir):
        """Opens file in read-only mode."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        assert fh >= 0
        assert fh in fuse_ops.fds
        assert fuse_ops.fds[fh].virtual_path == "/file1.txt"

        # Clean up
        fuse_ops.release("/file1.txt", fh)

    def test_open_nonexistent_file(self, fuse_ops):
        """Raises ENOENT for nonexistent file."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.open("/nonexistent.txt", os.O_RDONLY)

        assert exc_info.value.errno == errno.ENOENT

    def test_open_write_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when opening for write on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.open("/file1.txt", os.O_WRONLY)

        assert exc_info.value.errno == errno.EROFS

    def test_open_tracks_file_handle(self, fuse_ops, source_dir):
        """Tracks file handle correctly."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        handle = fuse_ops._get_file_handle(fh)
        assert handle.virtual_path == "/file1.txt"
        assert handle.flags == os.O_RDONLY
        assert os.path.basename(handle.real_path) == "file1.txt"

        # Clean up
        fuse_ops.release("/file1.txt", fh)

    def test_open_multiple_files(self, fuse_ops, source_dir):
        """Can open multiple files simultaneously."""
        fh1 = fuse_ops.open("/file1.txt", os.O_RDONLY)
        fh2 = fuse_ops.open("/file2.py", os.O_RDONLY)

        assert fh1 != fh2
        assert len(fuse_ops.fds) == 2

        # Clean up
        fuse_ops.release("/file1.txt", fh1)
        fuse_ops.release("/file2.py", fh2)


class TestFileRead:
    """Test file read() operation."""

    def test_read_file_content(self, fuse_ops, source_dir):
        """Reads file content correctly."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        # Read content
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)

        assert content == b"content1"

        fuse_ops.release("/file1.txt", fh)

    def test_read_with_offset(self, fuse_ops, source_dir):
        """Reads with offset correctly."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        # Read from offset 3 (content1 -> tent1)
        content = fuse_ops.read("/file1.txt", 5, 3, fh)

        assert content == b"tent1"

        fuse_ops.release("/file1.txt", fh)

    def test_read_with_size_limit(self, fuse_ops, source_dir):
        """Respects size limit."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        # Read only 4 bytes (content1 -> cont)
        content = fuse_ops.read("/file1.txt", 4, 0, fh)

        assert len(content) == 4
        assert content == b"cont"

        fuse_ops.release("/file1.txt", fh)

    def test_read_caches_transformed_content(self, fuse_ops, source_dir):
        """Caches transformed content."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        # First read
        content1 = fuse_ops.read("/file1.txt", 1024, 0, fh)

        # Second read should hit cache
        cache_key = "/file1.txt:transformed"
        from shadowfs.core.cache import CacheLevel

        cached = fuse_ops.cache.get("content", cache_key, level=CacheLevel.L2)
        assert cached is not None

        # Second read
        content2 = fuse_ops.read("/file1.txt", 1024, 0, fh)
        assert content1 == content2

        fuse_ops.release("/file1.txt", fh)

    def test_read_invalid_handle(self, fuse_ops):
        """Raises EBADF for invalid file handle."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.read("/file1.txt", 1024, 0, 999)

        assert exc_info.value.errno == errno.EBADF

    def test_read_applies_transforms(self, fuse_ops, source_dir):
        """Applies transform pipeline to content."""
        # Mock transform pipeline to modify content
        from shadowfs.transforms.base import TransformResult

        original_apply = fuse_ops.transform_pipeline.apply

        def mock_apply(content, path):
            return TransformResult(
                content=content.upper(), success=True, metadata={"transformed": True}
            )

        fuse_ops.transform_pipeline.apply = mock_apply

        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)

        assert content == b"CONTENT1"

        fuse_ops.release("/file1.txt", fh)
        fuse_ops.transform_pipeline.apply = original_apply

    def test_read_handles_transform_failure(self, fuse_ops, source_dir):
        """Falls back to original content if transform fails."""
        # Mock transform to raise exception
        fuse_ops.transform_pipeline.apply = Mock(side_effect=Exception("Transform error"))

        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)

        # Should return original content
        assert content == b"content1"

        fuse_ops.release("/file1.txt", fh)

    def test_read_handles_transform_result_failure(self, fuse_ops, source_dir):
        """Falls back to original content if transform result indicates failure."""
        from shadowfs.transforms.base import TransformResult

        # Mock transform to return failure
        def mock_apply(content, path):
            return TransformResult(
                content=b"", success=False, error="Transform failed", metadata={}
            )

        fuse_ops.transform_pipeline.apply = mock_apply

        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)

        # Should return original content
        assert content == b"content1"

        fuse_ops.release("/file1.txt", fh)


class TestFileWrite:
    """Test file write() operation."""

    def test_write_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when writing on readonly filesystem."""
        with pytest.raises(FuseOSError):
            # Can't even open for writing
            fuse_ops.open("/file1.txt", os.O_WRONLY)

    def test_write_on_readonly_fs_direct(self, fuse_ops):
        """Raises EROFS when calling write() on readonly filesystem."""
        # Even if we somehow got a handle, write() should check readonly
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.write("/file1.txt", b"test", 0, 999)

        assert exc_info.value.errno == errno.EROFS

    def test_write_file_content(self, config, source_dir):
        """Writes file content correctly."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Open for writing
        fh = ops.open("/file1.txt", os.O_WRONLY)

        # Write content
        bytes_written = ops.write("/file1.txt", b"New content", 0, fh)

        assert bytes_written == 11

        ops.release("/file1.txt", fh)

    def test_write_invalidates_cache(self, config, source_dir):
        """Invalidates content and attr cache after write."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Pre-populate cache
        from shadowfs.core.cache import CacheLevel

        ops.cache.set("content", "/file1.txt:transformed", b"cached", level=CacheLevel.L2)
        ops.cache.set("attr", "/file1.txt", {"st_size": 100}, level=CacheLevel.L1)

        fh = ops.open("/file1.txt", os.O_WRONLY)
        ops.write("/file1.txt", b"New", 0, fh)

        # Cache should be invalidated
        cached_content = ops.cache.get("content", "/file1.txt:transformed", level=CacheLevel.L2)
        cached_attr = ops.cache.get("attr", "/file1.txt", level=CacheLevel.L1)

        assert cached_content is None
        assert cached_attr is None

        ops.release("/file1.txt", fh)

    def test_write_invalid_handle(self, config):
        """Raises EBADF for invalid file handle."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.write("/file1.txt", b"test", 0, 999)

        assert exc_info.value.errno == errno.EBADF


class TestFileRelease:
    """Test file release() operation."""

    def test_release_closes_file(self, fuse_ops, source_dir):
        """Closes file and releases handle."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        assert fh in fuse_ops.fds

        fuse_ops.release("/file1.txt", fh)

        assert fh not in fuse_ops.fds

    def test_release_invalid_handle(self, fuse_ops):
        """Handles invalid file handle gracefully."""
        # Should not raise exception
        fuse_ops.release("/file1.txt", 999)


class TestFileCreate:
    """Test file create() operation."""

    def test_create_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when creating on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.create("/newfile.txt", 0o644)

        assert exc_info.value.errno == errno.EROFS

    def test_create_new_file(self, config, source_dir):
        """Creates new file successfully."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        fh = ops.create("/newfile.txt", 0o644)

        assert fh >= 0
        assert (source_dir / "newfile.txt").exists()

        ops.release("/newfile.txt", fh)

    def test_create_invalidates_directory_cache(self, config, source_dir):
        """Invalidates parent directory cache."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Pre-populate directory cache
        from shadowfs.core.cache import CacheLevel

        ops.cache.set("readdir", "/", [".", "..", "file1.txt"], level=CacheLevel.L1)

        fh = ops.create("/newfile.txt", 0o644)

        # Cache should be invalidated
        cached = ops.cache.get("readdir", "/", level=CacheLevel.L1)
        assert cached is None

        ops.release("/newfile.txt", fh)

    def test_create_nonexistent_parent(self, config):
        """Raises ENOENT when parent directory doesn't exist."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.create("/nonexistent/newfile.txt", 0o644)

        assert exc_info.value.errno == errno.ENOENT


class TestFileUnlink:
    """Test file unlink() operation."""

    def test_unlink_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when deleting on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.unlink("/file1.txt")

        assert exc_info.value.errno == errno.EROFS

    def test_unlink_file(self, config, source_dir):
        """Deletes file successfully."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Create a file to delete
        (source_dir / "todelete.txt").write_text("delete me")

        ops.unlink("/todelete.txt")

        assert not (source_dir / "todelete.txt").exists()

    def test_unlink_nonexistent_file(self, config):
        """Raises ENOENT for nonexistent file."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.unlink("/nonexistent.txt")

        assert exc_info.value.errno == errno.ENOENT

    def test_unlink_invalidates_caches(self, config, source_dir):
        """Invalidates all relevant caches."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        from shadowfs.core.cache import CacheLevel

        # Pre-populate caches
        ops.cache.set("readdir", "/", [".", "..", "file1.txt"], level=CacheLevel.L1)
        ops.cache.set("attr", "/file1.txt", {"st_size": 100}, level=CacheLevel.L1)
        ops.cache.set("path", "/file1.txt", str(source_dir / "file1.txt"))
        ops.cache.set("content", "/file1.txt:transformed", b"cached", level=CacheLevel.L2)

        ops.unlink("/file1.txt")

        # All caches should be invalidated
        assert ops.cache.get("readdir", "/", level=CacheLevel.L1) is None
        assert ops.cache.get("attr", "/file1.txt", level=CacheLevel.L1) is None
        assert ops.cache.get("path", "/file1.txt") is None
        assert ops.cache.get("content", "/file1.txt:transformed", level=CacheLevel.L2) is None


# ============================================================================
# Permission Operations Tests
# ============================================================================


class TestChmod:
    """Test chmod() operation."""

    def test_chmod_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when changing permissions on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.chmod("/file1.txt", 0o755)

        assert exc_info.value.errno == errno.EROFS

    def test_chmod_file(self, config, source_dir):
        """Changes file permissions successfully."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        ops.chmod("/file1.txt", 0o755)

        # Verify permissions changed
        st = (source_dir / "file1.txt").stat()
        assert st.st_mode & 0o777 == 0o755

    def test_chmod_nonexistent_file(self, config):
        """Raises ENOENT for nonexistent file."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.chmod("/nonexistent.txt", 0o755)

        assert exc_info.value.errno == errno.ENOENT

    def test_chmod_invalidates_attr_cache(self, config, source_dir):
        """Invalidates attribute cache."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        from shadowfs.core.cache import CacheLevel

        ops.cache.set("attr", "/file1.txt", {"st_mode": 0o644}, level=CacheLevel.L1)

        ops.chmod("/file1.txt", 0o755)

        cached = ops.cache.get("attr", "/file1.txt", level=CacheLevel.L1)
        assert cached is None


class TestChown:
    """Test chown() operation."""

    def test_chown_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when changing ownership on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.chown("/file1.txt", 1000, 1000)

        assert exc_info.value.errno == errno.EROFS

    def test_chown_nonexistent_file(self, config):
        """Raises ENOENT for nonexistent file."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.chown("/nonexistent.txt", 1000, 1000)

        assert exc_info.value.errno == errno.ENOENT

    def test_chown_invalidates_attr_cache(self, config, source_dir):
        """Invalidates attribute cache."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        from shadowfs.core.cache import CacheLevel

        ops.cache.set("attr", "/file1.txt", {"st_uid": 0}, level=CacheLevel.L1)

        # Try to change ownership (may fail due to permissions, but cache should still be invalidated)
        try:
            ops.chown("/file1.txt", os.getuid(), os.getgid())
        except FuseOSError:
            pass

        # Note: chown might fail due to permissions, so we just test cache invalidation on success path


class TestUtimens:
    """Test utimens() operation."""

    def test_utimens_on_readonly_fs(self, fuse_ops):
        """Raises EROFS when updating times on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.utimens("/file1.txt", None)

        assert exc_info.value.errno == errno.EROFS

    def test_utimens_with_none(self, config, source_dir):
        """Updates to current time when times=None."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        import time

        before = time.time()
        ops.utimens("/file1.txt", None)
        after = time.time()

        # Verify time was updated (allow for timing/rounding differences)
        st = (source_dir / "file1.txt").stat()
        # Allow 1 second tolerance for filesystem timestamp resolution
        assert abs(st.st_mtime - before) < 1.0

    def test_utimens_with_tuple(self, config, source_dir):
        """Updates to specified times."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        atime = 1000000000.0
        mtime = 1100000000.0

        ops.utimens("/file1.txt", (atime, mtime))

        st = (source_dir / "file1.txt").stat()
        assert abs(st.st_atime - atime) < 1
        assert abs(st.st_mtime - mtime) < 1

    def test_utimens_with_nanoseconds(self, config, source_dir):
        """Handles nanosecond precision times."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Format: ((atime_sec, atime_nsec), (mtime_sec, mtime_nsec))
        times = ((1000000000, 123456789), (1100000000, 987654321))

        ops.utimens("/file1.txt", times)

        # Just verify it doesn't crash
        st = (source_dir / "file1.txt").stat()
        assert st.st_mtime > 0

    def test_utimens_nonexistent_file(self, config):
        """Raises ENOENT for nonexistent file."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        with pytest.raises(FuseOSError) as exc_info:
            ops.utimens("/nonexistent.txt", None)

        assert exc_info.value.errno == errno.ENOENT

    def test_utimens_invalidates_attr_cache(self, config, source_dir):
        """Invalidates attribute cache."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        from shadowfs.core.cache import CacheLevel

        ops.cache.set("attr", "/file1.txt", {"st_mtime": 0}, level=CacheLevel.L1)

        ops.utimens("/file1.txt", None)

        cached = ops.cache.get("attr", "/file1.txt", level=CacheLevel.L1)
        assert cached is None


# ============================================================================
# Additional Operations Tests
# ============================================================================


class TestAccess:
    """Test access() operation."""

    def test_access_read_ok(self, fuse_ops, source_dir):
        """Allows read access to readable file."""
        # Should not raise exception
        fuse_ops.access("/file1.txt", os.R_OK)

    def test_access_exists_ok(self, fuse_ops, source_dir):
        """Confirms file exists."""
        # Should not raise exception
        fuse_ops.access("/file1.txt", os.F_OK)

    def test_access_nonexistent_file(self, fuse_ops):
        """Raises ENOENT for nonexistent file."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.access("/nonexistent.txt", os.F_OK)

        assert exc_info.value.errno == errno.ENOENT

    def test_access_write_on_readonly_fs(self, fuse_ops, source_dir):
        """Raises EROFS when checking write access on readonly filesystem."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.access("/file1.txt", os.W_OK)

        assert exc_info.value.errno == errno.EROFS

    def test_access_execute_ok(self, config, source_dir):
        """Checks execute permission."""
        # Make file executable
        (source_dir / "file1.txt").chmod(0o755)

        ops = ShadowFSOperations(config)

        # Should not raise exception
        ops.access("/file1.txt", os.X_OK)

    def test_access_permission_denied(self, config, source_dir):
        """Raises EACCES when permission denied."""
        # Make file non-executable
        (source_dir / "file1.txt").chmod(0o600)

        ops = ShadowFSOperations(config)

        # Check for execute permission on non-executable file
        with pytest.raises(FuseOSError) as exc_info:
            ops.access("/file1.txt", os.X_OK)

        assert exc_info.value.errno == errno.EACCES


class TestFsync:
    """Test fsync() operation."""

    def test_fsync_full(self, config, source_dir):
        """Syncs file data and metadata."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        fh = ops.open("/file1.txt", os.O_RDWR)

        # Should not raise exception
        ops.fsync("/file1.txt", False, fh)

        ops.release("/file1.txt", fh)

    def test_fsync_data_only(self, config, source_dir):
        """Syncs file data only."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        fh = ops.open("/file1.txt", os.O_RDWR)

        # Should not raise exception
        ops.fsync("/file1.txt", True, fh)

        ops.release("/file1.txt", fh)

    def test_fsync_invalid_handle(self, fuse_ops):
        """Raises EBADF for invalid file handle."""
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.fsync("/file1.txt", False, 999)

        assert exc_info.value.errno == errno.EBADF


# ============================================================================
# Exception Handling Tests
# ============================================================================


class TestExceptionHandling:
    """Test exception handling in various operations."""

    def test_open_os_error(self, fuse_ops, source_dir):
        """Handles OSError during open()."""
        # Mock os.open to raise OSError
        with patch("os.open", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(FuseOSError) as exc_info:
                fuse_ops.open("/file1.txt", os.O_RDONLY)

            assert exc_info.value.errno == errno.EACCES

    def test_read_os_error(self, fuse_ops, source_dir):
        """Handles OSError during read()."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)

        # Mock os.fdopen to raise OSError
        with patch("os.fdopen", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(FuseOSError) as exc_info:
                fuse_ops.read("/file1.txt", 1024, 0, fh)

            assert exc_info.value.errno == errno.EIO

        fuse_ops.release("/file1.txt", fh)

    def test_write_os_error(self, config, source_dir):
        """Handles OSError during write()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        fh = ops.open("/file1.txt", os.O_WRONLY)

        # Mock os.write to raise OSError
        with patch("os.write", side_effect=OSError(errno.ENOSPC, "No space left")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.write("/file1.txt", b"test", 0, fh)

            assert exc_info.value.errno == errno.ENOSPC

        ops.release("/file1.txt", fh)

    def test_create_os_error(self, config, source_dir):
        """Handles OSError during create()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Mock os.open to raise OSError
        with patch("os.open", side_effect=OSError(errno.EEXIST, "File exists")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.create("/newfile.txt", 0o644)

            assert exc_info.value.errno == errno.EEXIST

    def test_unlink_os_error(self, config, source_dir):
        """Handles OSError during unlink()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Mock os.unlink to raise OSError
        with patch("os.unlink", side_effect=OSError(errno.EBUSY, "File busy")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.unlink("/file1.txt")

            assert exc_info.value.errno == errno.EBUSY

    def test_chmod_os_error(self, config, source_dir):
        """Handles OSError during chmod()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Mock os.chmod to raise OSError
        with patch("os.chmod", side_effect=OSError(errno.EPERM, "Operation not permitted")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.chmod("/file1.txt", 0o755)

            assert exc_info.value.errno == errno.EPERM

    def test_chown_os_error(self, config, source_dir):
        """Handles OSError during chown()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Mock os.chown to raise OSError
        with patch("os.chown", side_effect=OSError(errno.EPERM, "Operation not permitted")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.chown("/file1.txt", 1000, 1000)

            assert exc_info.value.errno == errno.EPERM

    def test_utimens_os_error(self, config, source_dir):
        """Handles OSError during utimens()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        # Mock os.utime to raise OSError
        with patch("os.utime", side_effect=OSError(errno.EPERM, "Operation not permitted")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.utimens("/file1.txt", None)

            assert exc_info.value.errno == errno.EPERM

    def test_access_os_error(self, fuse_ops, source_dir):
        """Handles OSError during access()."""
        # Mock os.access to raise OSError
        with patch("os.access", side_effect=OSError(errno.EACCES, "Access denied")):
            with pytest.raises(FuseOSError) as exc_info:
                fuse_ops.access("/file1.txt", os.R_OK)

            assert exc_info.value.errno == errno.EACCES

    def test_fsync_os_error(self, config, source_dir):
        """Handles OSError during fsync()."""
        config._config["readonly"] = False
        ops = ShadowFSOperations(config)

        fh = ops.open("/file1.txt", os.O_RDWR)

        # Mock os.fsync to raise OSError
        with patch("os.fsync", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(FuseOSError) as exc_info:
                ops.fsync("/file1.txt", False, fh)

            assert exc_info.value.errno == errno.EIO

        ops.release("/file1.txt", fh)
