"""
Tests for ShadowFS VirtualLayerManager.

Tests the central coordinator for all virtual layer operations.
Target: 95%+ coverage, 60+ tests
"""

import tempfile
from pathlib import Path

import pytest

from shadowfs.integration.virtual_layers.base import FileInfo, VirtualLayer
from shadowfs.integration.virtual_layers.classifier_layer import (
    BuiltinClassifiers as ClassifierBuiltins,
)
from shadowfs.integration.virtual_layers.classifier_layer import ClassifierLayer
from shadowfs.integration.virtual_layers.date_layer import DateLayer
from shadowfs.integration.virtual_layers.manager import LayerFactory, VirtualLayerManager
from shadowfs.integration.virtual_layers.tag_layer import TagLayer


class MockLayer(VirtualLayer):
    """Mock layer for testing."""

    def __init__(self, name):
        """Initialize mock layer."""
        super().__init__(name)
        self.build_index_called = False
        self.build_index_files = None

    def build_index(self, files):
        """Build index (mock implementation)."""
        self.build_index_called = True
        self.build_index_files = files

    def resolve(self, virtual_path):
        """Resolve path (mock implementation)."""
        return f"/mock/{self.name}/{virtual_path}"

    def list_directory(self, subpath=""):
        """List directory (mock implementation)."""
        if not subpath:
            return ["cat1", "cat2"]
        return ["file1.txt", "file2.txt"]


class TestManagerBasics:
    """Test VirtualLayerManager basic functionality."""

    def test_create_manager_empty(self):
        """Test creating manager with no sources."""
        manager = VirtualLayerManager()

        assert manager.sources == []
        assert manager.layers == {}
        assert manager.files == []

    def test_create_manager_with_sources(self):
        """Test creating manager with source list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = VirtualLayerManager([tmpdir])

            assert manager.sources == [tmpdir]
            assert manager.layers == {}
            assert manager.files == []

    def test_add_source_valid(self):
        """Test adding a valid source directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = VirtualLayerManager()
            manager.add_source(tmpdir)

            assert tmpdir in manager.sources

    def test_add_source_nonexistent_raises(self):
        """Test adding nonexistent source raises ValueError."""
        manager = VirtualLayerManager()

        with pytest.raises(ValueError, match="does not exist"):
            manager.add_source("/nonexistent/path")

    def test_add_source_not_directory_raises(self):
        """Test adding file instead of directory raises ValueError."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            manager = VirtualLayerManager()

            with pytest.raises(ValueError, match="not a directory"):
                manager.add_source(tmpfile.name)

    def test_add_source_duplicate_ignored(self):
        """Test adding duplicate source doesn't duplicate entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = VirtualLayerManager()
            manager.add_source(tmpdir)
            manager.add_source(tmpdir)

            assert manager.sources == [tmpdir]

    def test_clear_all(self):
        """Test clearing all manager state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = VirtualLayerManager([tmpdir])
            layer = MockLayer("test")
            manager.add_layer(layer)
            manager.files = [FileInfo.from_path(__file__)]

            manager.clear_all()

            assert manager.sources == []
            assert manager.layers == {}
            assert manager.files == []


class TestLayerManagement:
    """Test layer registration and management."""

    def test_add_layer(self):
        """Test adding a layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")

        manager.add_layer(layer)

        assert "test" in manager.layers
        assert manager.layers["test"] is layer

    def test_add_layer_duplicate_name_raises(self):
        """Test adding layer with duplicate name raises ValueError."""
        manager = VirtualLayerManager()
        layer1 = MockLayer("test")
        layer2 = MockLayer("test")

        manager.add_layer(layer1)

        with pytest.raises(ValueError, match="already registered"):
            manager.add_layer(layer2)

    def test_remove_layer(self):
        """Test removing a layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        manager.remove_layer("test")

        assert "test" not in manager.layers

    def test_remove_layer_nonexistent_raises(self):
        """Test removing nonexistent layer raises KeyError."""
        manager = VirtualLayerManager()

        with pytest.raises(KeyError, match="not found"):
            manager.remove_layer("nonexistent")

    def test_get_layer_exists(self):
        """Test getting an existing layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        result = manager.get_layer("test")

        assert result is layer

    def test_get_layer_nonexistent(self):
        """Test getting nonexistent layer returns None."""
        manager = VirtualLayerManager()

        result = manager.get_layer("nonexistent")

        assert result is None

    def test_list_layers_empty(self):
        """Test listing layers when none registered."""
        manager = VirtualLayerManager()

        result = manager.list_layers()

        assert result == []

    def test_list_layers_multiple(self):
        """Test listing multiple layers in sorted order."""
        manager = VirtualLayerManager()
        manager.add_layer(MockLayer("zebra"))
        manager.add_layer(MockLayer("alpha"))
        manager.add_layer(MockLayer("beta"))

        result = manager.list_layers()

        assert result == ["alpha", "beta", "zebra"]


class TestSourceScanning:
    """Test source directory scanning."""

    def test_scan_sources_empty(self):
        """Test scanning with no sources."""
        manager = VirtualLayerManager()

        manager.scan_sources()

        assert manager.files == []

    def test_scan_sources_single_file(self):
        """Test scanning directory with single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            assert len(manager.files) == 1
            assert manager.files[0].name == "test.txt"
            assert manager.files[0].path == "test.txt"

    def test_scan_sources_multiple_files(self):
        """Test scanning directory with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "file1.txt").write_text("content1")
            (Path(tmpdir) / "file2.txt").write_text("content2")
            (Path(tmpdir) / "file3.txt").write_text("content3")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            assert len(manager.files) == 3
            names = {f.name for f in manager.files}
            assert names == {"file1.txt", "file2.txt", "file3.txt"}

    def test_scan_sources_nested_directories(self):
        """Test scanning nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (Path(tmpdir) / "root.txt").write_text("root")
            (subdir / "nested.txt").write_text("nested")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            assert len(manager.files) == 2
            paths = {f.path for f in manager.files}
            assert "root.txt" in paths
            assert "subdir/nested.txt" in paths or "subdir\\nested.txt" in paths

    def test_scan_sources_multiple_source_dirs(self):
        """Test scanning multiple source directories."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            # Create files in each source
            (Path(tmpdir1) / "file1.txt").write_text("content1")
            (Path(tmpdir2) / "file2.txt").write_text("content2")

            manager = VirtualLayerManager([tmpdir1, tmpdir2])
            manager.scan_sources()

            assert len(manager.files) == 2
            names = {f.name for f in manager.files}
            assert names == {"file1.txt", "file2.txt"}

    def test_scan_sources_creates_file_info_objects(self):
        """Test that scan creates proper FileInfo objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            file_info = manager.files[0]
            assert file_info.name == "test.txt"
            assert file_info.size > 0
            assert file_info.mtime > 0
            assert file_info.is_file


class TestIndexBuilding:
    """Test index building for layers."""

    def test_rebuild_indexes_calls_all_layers(self):
        """Test that rebuild_indexes calls build_index on all layers."""
        manager = VirtualLayerManager()
        layer1 = MockLayer("layer1")
        layer2 = MockLayer("layer2")
        manager.add_layer(layer1)
        manager.add_layer(layer2)

        manager.rebuild_indexes()

        assert layer1.build_index_called
        assert layer2.build_index_called

    def test_rebuild_indexes_passes_files(self):
        """Test that rebuild_indexes passes file list to layers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.txt").write_text("content")

            manager = VirtualLayerManager([tmpdir])
            layer = MockLayer("test")
            manager.add_layer(layer)

            manager.scan_sources()
            manager.rebuild_indexes()

            assert layer.build_index_files is manager.files
            assert len(layer.build_index_files) == 1

    def test_rebuild_indexes_empty_files(self):
        """Test rebuild_indexes with no files scanned."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        manager.rebuild_indexes()

        assert layer.build_index_called
        assert layer.build_index_files == []


class TestPathResolution:
    """Test path resolution routing."""

    def test_resolve_path_empty_returns_none(self):
        """Test resolving empty path returns None."""
        manager = VirtualLayerManager()

        result = manager.resolve_path("")

        assert result is None

    def test_resolve_path_nonexistent_layer_returns_none(self):
        """Test resolving with nonexistent layer returns None."""
        manager = VirtualLayerManager()

        result = manager.resolve_path("nonexistent/file.txt")

        assert result is None

    def test_resolve_path_layer_only_returns_none(self):
        """Test resolving path with only layer name returns None."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        result = manager.resolve_path("test")

        assert result is None

    def test_resolve_path_delegates_to_layer(self):
        """Test that resolve_path delegates to the layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        result = manager.resolve_path("test/subpath/file.txt")

        assert result == "/mock/test/subpath/file.txt"

    def test_resolve_path_with_real_layer(self):
        """Test path resolution with real layer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            # Set up manager with date layer
            manager = VirtualLayerManager([tmpdir])
            layer = DateLayer("by-date")
            manager.add_layer(layer)

            manager.scan_sources()
            manager.rebuild_indexes()

            # Get date components from file
            import datetime

            dt = datetime.datetime.fromtimestamp(test_file.stat().st_mtime)
            year = str(dt.year)
            month = f"{dt.month:02d}"
            day = f"{dt.day:02d}"

            # Resolve path
            virtual_path = f"by-date/{year}/{month}/{day}/test.txt"
            result = manager.resolve_path(virtual_path)

            assert result == str(test_file)


class TestDirectoryListing:
    """Test directory listing functionality."""

    def test_list_directory_root_empty(self):
        """Test listing root with no layers."""
        manager = VirtualLayerManager()

        result = manager.list_directory("")

        assert result == []

    def test_list_directory_root_lists_layers(self):
        """Test listing root returns layer names."""
        manager = VirtualLayerManager()
        manager.add_layer(MockLayer("zebra"))
        manager.add_layer(MockLayer("alpha"))

        result = manager.list_directory("")

        assert result == ["alpha", "zebra"]

    def test_list_directory_nonexistent_layer_returns_empty(self):
        """Test listing nonexistent layer returns empty list."""
        manager = VirtualLayerManager()

        result = manager.list_directory("nonexistent")

        assert result == []

    def test_list_directory_layer_root(self):
        """Test listing layer root delegates to layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        result = manager.list_directory("test")

        assert result == ["cat1", "cat2"]

    def test_list_directory_layer_subpath(self):
        """Test listing layer subpath delegates to layer."""
        manager = VirtualLayerManager()
        layer = MockLayer("test")
        manager.add_layer(layer)

        result = manager.list_directory("test/cat1")

        assert result == ["file1.txt", "file2.txt"]

    def test_list_directory_with_real_layer(self):
        """Test directory listing with real layer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "file1.py").write_text("code")
            (Path(tmpdir) / "file2.py").write_text("code")
            (Path(tmpdir) / "doc.md").write_text("doc")

            # Set up manager with extension layer
            manager = VirtualLayerManager([tmpdir])
            layer = ClassifierLayer("by-type", ClassifierBuiltins.extension)
            manager.add_layer(layer)

            manager.scan_sources()
            manager.rebuild_indexes()

            # List root should show layer
            assert manager.list_directory("") == ["by-type"]

            # List layer should show categories
            categories = manager.list_directory("by-type")
            assert "py" in categories
            assert "md" in categories


class TestStatistics:
    """Test manager statistics."""

    def test_get_stats_empty(self):
        """Test statistics for empty manager."""
        manager = VirtualLayerManager()

        stats = manager.get_stats()

        assert stats["source_count"] == 0
        assert stats["layer_count"] == 0
        assert stats["file_count"] == 0

    def test_get_stats_with_sources(self):
        """Test statistics with sources added."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            manager = VirtualLayerManager([tmpdir1, tmpdir2])

            stats = manager.get_stats()

            assert stats["source_count"] == 2

    def test_get_stats_with_layers(self):
        """Test statistics with layers registered."""
        manager = VirtualLayerManager()
        manager.add_layer(MockLayer("layer1"))
        manager.add_layer(MockLayer("layer2"))
        manager.add_layer(MockLayer("layer3"))

        stats = manager.get_stats()

        assert stats["layer_count"] == 3

    def test_get_stats_with_files(self):
        """Test statistics with files scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.txt").write_text("content")
            (Path(tmpdir) / "file2.txt").write_text("content")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            stats = manager.get_stats()

            assert stats["file_count"] == 2


class TestLayerFactory:
    """Test LayerFactory helper functions."""

    def test_create_date_layer_defaults(self):
        """Test creating date layer with default parameters."""
        layer = LayerFactory.create_date_layer()

        assert layer.name == "by-date"
        assert isinstance(layer, DateLayer)

    def test_create_date_layer_custom(self):
        """Test creating date layer with custom parameters."""
        layer = LayerFactory.create_date_layer("by-modified", "mtime")

        assert layer.name == "by-modified"
        assert isinstance(layer, DateLayer)

    def test_create_extension_layer_default(self):
        """Test creating extension layer with default name."""
        layer = LayerFactory.create_extension_layer()

        assert layer.name == "by-type"
        assert isinstance(layer, ClassifierLayer)

    def test_create_extension_layer_custom_name(self):
        """Test creating extension layer with custom name."""
        layer = LayerFactory.create_extension_layer("by-file-type")

        assert layer.name == "by-file-type"

    def test_create_size_layer_default(self):
        """Test creating size layer with default name."""
        layer = LayerFactory.create_size_layer()

        assert layer.name == "by-size"
        assert isinstance(layer, ClassifierLayer)

    def test_create_size_layer_custom_name(self):
        """Test creating size layer with custom name."""
        layer = LayerFactory.create_size_layer("by-file-size")

        assert layer.name == "by-file-size"

    def test_create_tag_layer_default(self):
        """Test creating tag layer with default parameters."""
        layer = LayerFactory.create_tag_layer()

        assert layer.name == "by-tag"
        assert isinstance(layer, TagLayer)

    def test_create_tag_layer_custom(self):
        """Test creating tag layer with custom parameters."""
        from shadowfs.integration.virtual_layers.tag_layer import BuiltinExtractors

        extractors = [BuiltinExtractors.sidecar(".tags")]
        layer = LayerFactory.create_tag_layer("by-label", extractors)

        assert layer.name == "by-label"
        assert layer.extractors == extractors


class TestIntegration:
    """Integration tests with real layers and files."""

    def test_full_workflow(self):
        """Test complete workflow: scan, add layers, build indexes, query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "code.py").write_text("print('hello')")
            (Path(tmpdir) / "doc.md").write_text("# Documentation")
            (Path(tmpdir) / "data.json").write_text("{}")

            # Set up manager
            manager = VirtualLayerManager([tmpdir])

            # Add layers
            manager.add_layer(LayerFactory.create_extension_layer())
            manager.add_layer(LayerFactory.create_size_layer())

            # Scan and build
            manager.scan_sources()
            manager.rebuild_indexes()

            # Verify stats
            stats = manager.get_stats()
            assert stats["source_count"] == 1
            assert stats["layer_count"] == 2
            assert stats["file_count"] == 3

            # Verify layer listing
            assert set(manager.list_directory("")) == {"by-size", "by-type"}

            # Verify type layer
            type_categories = manager.list_directory("by-type")
            assert "py" in type_categories
            assert "md" in type_categories
            assert "json" in type_categories

    def test_multiple_layers_same_files(self):
        """Test multiple layers indexing the same files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("code")

            # Set up manager with multiple layers
            manager = VirtualLayerManager([tmpdir])
            manager.add_layer(LayerFactory.create_extension_layer())
            manager.add_layer(LayerFactory.create_size_layer())
            manager.add_layer(LayerFactory.create_date_layer())

            manager.scan_sources()
            manager.rebuild_indexes()

            # File should be accessible through all layers
            stats = manager.get_stats()
            assert stats["layer_count"] == 3
            assert stats["file_count"] == 1

            # Check each layer has content
            assert len(manager.list_directory("by-type")) > 0
            assert len(manager.list_directory("by-size")) > 0
            assert len(manager.list_directory("by-date")) > 0

    def test_rescan_updates_files(self):
        """Test rescanning updates file list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial file
            (Path(tmpdir) / "file1.txt").write_text("content")

            manager = VirtualLayerManager([tmpdir])
            manager.scan_sources()

            assert len(manager.files) == 1

            # Add more files
            (Path(tmpdir) / "file2.txt").write_text("content")
            (Path(tmpdir) / "file3.txt").write_text("content")

            # Rescan
            manager.scan_sources()

            assert len(manager.files) == 3

    def test_layer_removal_and_readd(self):
        """Test removing and re-adding layers."""
        manager = VirtualLayerManager()
        layer1 = MockLayer("test")

        # Add layer
        manager.add_layer(layer1)
        assert "test" in manager.layers

        # Remove layer
        manager.remove_layer("test")
        assert "test" not in manager.layers

        # Re-add layer
        layer2 = MockLayer("test")
        manager.add_layer(layer2)
        assert "test" in manager.layers
        assert manager.layers["test"] is layer2

    def test_scan_sources_with_permission_error(self, tmp_path, monkeypatch):
        """Test scan_sources gracefully handles files that can't be read."""
        src = tmp_path / "source"
        src.mkdir()

        # Create some normal files
        (src / "file1.txt").write_text("content 1")
        (src / "file2.txt").write_text("content 2")

        # Mock FileInfo.from_path to raise PermissionError for file2
        original_from_path = FileInfo.from_path

        def mock_from_path(real_path, source_root):
            if "file2.txt" in real_path:
                raise PermissionError("Access denied")
            return original_from_path(real_path, source_root)

        monkeypatch.setattr(FileInfo, "from_path", mock_from_path)

        manager = VirtualLayerManager([str(src)])
        manager.scan_sources()

        # Should only have file1, file2 should be skipped
        assert len(manager.files) == 1
        assert manager.files[0].name == "file1.txt"
