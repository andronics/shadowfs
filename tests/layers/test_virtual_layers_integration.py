"""
Integration tests for the complete Virtual Layers system.

These tests verify end-to-end functionality with multiple layers active
simultaneously, cross-layer interactions, and real filesystem integration.
"""

import os
import time
from pathlib import Path

import pytest

from shadowfs.layers.classifier import BuiltinClassifiers, ClassifierLayer
from shadowfs.layers.date import DateLayer
from shadowfs.layers.hierarchical import BuiltinClassifiers as HierarchicalBuiltinClassifiers
from shadowfs.layers.hierarchical import HierarchicalLayer
from shadowfs.layers.manager import LayerFactory, LayerManager
from shadowfs.layers.tag import BuiltinExtractors, TagLayer


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows with virtual layers."""

    def test_basic_workflow(self, tmp_path):
        """Test basic workflow: create, scan, index, resolve."""
        # Create source structure
        src = tmp_path / "source"
        src.mkdir()
        (src / "file1.py").write_text("# Python file")
        (src / "file2.js").write_text("// JavaScript file")
        (src / "doc.md").write_text("# Markdown doc")

        # Create manager and add source
        manager = LayerManager()
        manager.add_source(str(src))

        # Add layers
        type_layer = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        manager.add_layer(type_layer)

        # Scan and index
        manager.scan_sources()
        manager.rebuild_indexes()

        # Verify resolution
        assert manager.resolve_path("by-type/py/file1.py") == str(src / "file1.py")
        assert manager.resolve_path("by-type/js/file2.js") == str(src / "file2.js")
        assert manager.resolve_path("by-type/md/doc.md") == str(src / "doc.md")

        # Verify directory listing
        assert set(manager.list_directory("")) == {"by-type"}
        assert set(manager.list_directory("by-type")) == {"py", "js", "md"}
        assert manager.list_directory("by-type/py") == ["file1.py"]

    def test_multiple_sources(self, tmp_path):
        """Test scanning multiple source directories."""
        # Create two source directories
        src1 = tmp_path / "source1"
        src2 = tmp_path / "source2"
        src1.mkdir()
        src2.mkdir()

        (src1 / "file1.txt").write_text("File 1")
        (src2 / "file2.txt").write_text("File 2")

        # Create manager with multiple sources
        manager = LayerManager([str(src1), str(src2)])
        manager.add_layer(ClassifierLayer("by-type", BuiltinClassifiers.extension))

        manager.scan_sources()
        manager.rebuild_indexes()

        # Verify both files are accessible
        assert manager.resolve_path("by-type/txt/file1.txt") == str(src1 / "file1.txt")
        assert manager.resolve_path("by-type/txt/file2.txt") == str(src2 / "file2.txt")
        assert set(manager.list_directory("by-type/txt")) == {"file1.txt", "file2.txt"}

    def test_complete_hierarchy(self, tmp_path):
        """Test complete directory hierarchy with nested structure."""
        # Create nested structure
        src = tmp_path / "source"
        (src / "project1" / "src").mkdir(parents=True)
        (src / "project1" / "tests").mkdir(parents=True)
        (src / "project2" / "src").mkdir(parents=True)

        (src / "project1" / "src" / "main.py").write_text("# Main")
        (src / "project1" / "tests" / "test_main.py").write_text("# Test")
        (src / "project2" / "src" / "app.py").write_text("# App")

        # Create manager with hierarchical layer
        manager = LayerManager([str(src)])
        layer = HierarchicalLayer(
            "by-project",
            [
                HierarchicalBuiltinClassifiers.by_path_component(0),
                HierarchicalBuiltinClassifiers.by_path_component(1),
            ],
        )
        manager.add_layer(layer)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Verify hierarchy
        assert set(manager.list_directory("by-project")) == {"project1", "project2"}
        assert set(manager.list_directory("by-project/project1")) == {"src", "tests"}
        assert manager.list_directory("by-project/project1/src") == ["main.py"]
        assert manager.list_directory("by-project/project1/tests") == ["test_main.py"]

    def test_layer_lifecycle(self, tmp_path):
        """Test adding and removing layers dynamically."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.py").write_text("# Python")

        manager = LayerManager([str(src)])
        manager.scan_sources()

        # Add first layer
        layer1 = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        manager.add_layer(layer1)
        manager.rebuild_indexes()

        assert "by-type" in manager.list_directory("")
        assert manager.resolve_path("by-type/py/file.py") == str(src / "file.py")

        # Add second layer
        layer2 = ClassifierLayer("by-size", BuiltinClassifiers.size)
        manager.add_layer(layer2)
        manager.rebuild_indexes()

        assert set(manager.list_directory("")) == {"by-type", "by-size"}

        # Remove first layer
        manager.remove_layer("by-type")

        assert manager.list_directory("") == ["by-size"]
        assert manager.resolve_path("by-type/py/file.py") is None


class TestMultipleLayersSimultaneously:
    """Test multiple virtual layers active at the same time."""

    def test_three_layers_active(self, tmp_path):
        """Test three different layer types active simultaneously."""
        # Create test files
        src = tmp_path / "source"
        src.mkdir()

        # Create files with different properties
        files = [
            ("doc1.md", "# Doc 1", "important,docs"),
            ("doc2.md", "# Doc 2", "docs"),
            ("code.py", "# Code", "important,code"),
        ]

        for filename, content, tags in files:
            (src / filename).write_text(content)
            # Create sidecar tag file (filename.tags)
            (src / f"{filename}.tags").write_text(tags)

        # Create manager with three different layer types
        manager = LayerManager([str(src)])

        # Layer 1: By extension
        type_layer = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        manager.add_layer(type_layer)

        # Layer 2: By date
        date_layer = DateLayer("by-date", "mtime")
        manager.add_layer(date_layer)

        # Layer 3: By tags
        tag_layer = TagLayer("by-tag", [BuiltinExtractors.sidecar(".tags")])
        manager.add_layer(tag_layer)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Verify all three layers exist
        assert set(manager.list_directory("")) == {"by-type", "by-date", "by-tag"}

        # Verify by-type layer
        assert "md" in manager.list_directory("by-type")
        assert "py" in manager.list_directory("by-type")

        # Verify by-tag layer
        assert "important" in manager.list_directory("by-tag")
        assert "docs" in manager.list_directory("by-tag")
        assert "code" in manager.list_directory("by-tag")

        # Verify by-date layer (should have year/month/day structure)
        years = manager.list_directory("by-date")
        assert len(years) >= 1  # At least one year

    def test_layer_independence(self, tmp_path):
        """Test that layers operate independently."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.txt").write_text("Test")

        manager = LayerManager([str(src)])

        # Add two independent layers
        layer1 = ClassifierLayer("layer1", BuiltinClassifiers.extension)
        layer2 = ClassifierLayer("layer2", BuiltinClassifiers.size)
        manager.add_layer(layer1)
        manager.add_layer(layer2)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Removing one layer shouldn't affect the other
        manager.remove_layer("layer1")

        assert manager.list_directory("") == ["layer2"]
        assert manager.get_layer("layer2") is not None
        assert manager.get_layer("layer1") is None


class TestCrossLayerInteractions:
    """Test interactions between multiple layers."""

    def test_same_file_multiple_layers(self, tmp_path):
        """Test that same file appears in multiple layers."""
        src = tmp_path / "source"
        src.mkdir()
        file_path = src / "important.txt"
        file_path.write_text("Important file")
        # Create sidecar tag file
        (src / "important.txt.tags").write_text("important")

        manager = LayerManager([str(src)])

        # Add multiple layers
        type_layer = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        size_layer = ClassifierLayer("by-size", BuiltinClassifiers.size)
        tag_layer = TagLayer("by-tag", [BuiltinExtractors.sidecar(".tags")])

        manager.add_layer(type_layer)
        manager.add_layer(size_layer)
        manager.add_layer(tag_layer)

        manager.scan_sources()
        manager.rebuild_indexes()

        # File should be accessible through all three layers
        type_path = manager.resolve_path("by-type/txt/important.txt")
        size_dirs = manager.list_directory("by-size")
        tag_path = manager.resolve_path("by-tag/important/important.txt")

        assert type_path == str(file_path)
        assert tag_path == str(file_path)
        assert len(size_dirs) > 0  # Should be in some size category

    def test_consistent_resolution(self, tmp_path):
        """Test that path resolution is consistent across layers."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.txt").write_text("Test content")

        manager = LayerManager([str(src)])

        # Add two layers that should both contain the file
        layer1 = ClassifierLayer("layer1", BuiltinClassifiers.extension)
        layer2 = ClassifierLayer("layer2", BuiltinClassifiers.size)

        manager.add_layer(layer1)
        manager.add_layer(layer2)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Both layers should resolve to the same real path
        path1 = manager.resolve_path("layer1/txt/file.txt")
        size_categories = manager.list_directory("layer2")
        # File should be in one of the size categories
        path2 = None
        for category in size_categories:
            if "file.txt" in manager.list_directory(f"layer2/{category}"):
                path2 = manager.resolve_path(f"layer2/{category}/file.txt")
                break

        assert path1 == str(src / "file.txt")
        assert path2 == str(src / "file.txt")
        assert path1 == path2

    def test_layer_specific_paths(self, tmp_path):
        """Test that each layer has its own path structure."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.py").write_text("# Python")

        manager = LayerManager([str(src)])

        # Add different layer types with different path structures
        type_layer = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        date_layer = DateLayer("by-date", "mtime")

        manager.add_layer(type_layer)
        manager.add_layer(date_layer)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Each layer should have different structure
        type_dirs = manager.list_directory("by-type")
        date_dirs = manager.list_directory("by-date")

        assert "py" in type_dirs  # Type layer has extensions
        assert all(d.isdigit() for d in date_dirs)  # Date layer has years


class TestRealFilesystemIntegration:
    """Test integration with real filesystem operations."""

    def test_real_file_operations(self, tmp_path):
        """Test with real file system operations."""
        # Create realistic directory structure
        src = tmp_path / "projects"
        (src / "app" / "src").mkdir(parents=True)
        (src / "app" / "tests").mkdir(parents=True)
        (src / "lib" / "utils").mkdir(parents=True)

        # Create various file types
        (src / "app" / "src" / "main.py").write_text("#!/usr/bin/env python3\nprint('Hello')")
        (src / "app" / "src" / "config.yaml").write_text("setting: value")
        (src / "app" / "tests" / "test_main.py").write_text("def test_main(): pass")
        (src / "lib" / "utils" / "helpers.py").write_text("def helper(): return True")
        (src / "README.md").write_text("# Project README")

        # Create manager
        manager = LayerManager([str(src)])

        # Add hierarchical layer by project and directory
        project_layer = HierarchicalLayer(
            "by-project",
            [
                HierarchicalBuiltinClassifiers.by_path_component(0),
                HierarchicalBuiltinClassifiers.by_path_component(1),
            ],
        )
        manager.add_layer(project_layer)

        # Add type layer
        type_layer = ClassifierLayer("by-type", BuiltinClassifiers.extension)
        manager.add_layer(type_layer)

        manager.scan_sources()
        manager.rebuild_indexes()

        # Verify real file access
        main_path = manager.resolve_path("by-project/app/src/main.py")
        assert Path(main_path).exists()
        assert Path(main_path).read_text().startswith("#!/usr/bin/env python3")

        readme_path = manager.resolve_path("by-type/md/README.md")
        assert Path(readme_path).exists()
        assert Path(readme_path).read_text().startswith("# Project README")

    def test_file_metadata_accuracy(self, tmp_path):
        """Test that file metadata is accurately captured."""
        src = tmp_path / "source"
        src.mkdir()
        file_path = src / "test.txt"
        content = "Test content"
        file_path.write_text(content)

        # Get actual file stats
        stat_info = os.stat(file_path)

        # Scan with manager
        manager = LayerManager([str(src)])
        manager.scan_sources()

        # Verify FileInfo metadata matches actual file
        assert len(manager.files) == 1
        file_info = manager.files[0]

        assert file_info.name == "test.txt"
        assert file_info.size == len(content)
        assert file_info.is_file is True
        assert abs(file_info.mtime - stat_info.st_mtime) < 1.0  # Within 1 second

    def test_symlink_handling(self, tmp_path):
        """Test handling of symbolic links."""
        src = tmp_path / "source"
        src.mkdir()

        # Create real file
        real_file = src / "real.txt"
        real_file.write_text("Real content")

        # Create symlink
        link_file = src / "link.txt"
        link_file.symlink_to(real_file)

        manager = LayerManager([str(src)])
        manager.scan_sources()

        # Both real file and symlink should be scanned
        # (behavior may vary based on FileInfo.from_path implementation)
        assert len(manager.files) >= 1  # At least the real file


class TestPerformance:
    """Performance benchmarks for virtual layers."""

    def create_large_filesystem(self, base_path: Path, num_files: int) -> None:
        """Create a large filesystem for performance testing."""
        # Create files distributed across directories
        files_per_dir = 100
        num_dirs = (num_files + files_per_dir - 1) // files_per_dir

        for dir_idx in range(num_dirs):
            dir_path = base_path / f"dir{dir_idx:04d}"
            dir_path.mkdir(exist_ok=True)

            files_in_this_dir = min(files_per_dir, num_files - dir_idx * files_per_dir)
            for file_idx in range(files_in_this_dir):
                file_path = dir_path / f"file{file_idx:04d}.txt"
                file_path.write_text(f"Content {dir_idx}-{file_idx}")

    def test_scan_1000_files(self, tmp_path, benchmark_enabled):
        """Benchmark scanning 1,000 files."""
        if not benchmark_enabled:
            pytest.skip("Benchmark tests disabled")

        src = tmp_path / "source"
        src.mkdir()
        self.create_large_filesystem(src, 1000)

        manager = LayerManager([str(src)])

        start = time.time()
        manager.scan_sources()
        scan_time = time.time() - start

        assert len(manager.files) == 1000
        assert scan_time < 5.0  # Should complete in under 5 seconds
        print(f"\nScan 1,000 files: {scan_time:.3f}s ({1000 / scan_time:.0f} files/sec)")

    def test_index_1000_files(self, tmp_path, benchmark_enabled):
        """Benchmark indexing 1,000 files."""
        if not benchmark_enabled:
            pytest.skip("Benchmark tests disabled")

        src = tmp_path / "source"
        src.mkdir()
        self.create_large_filesystem(src, 1000)

        manager = LayerManager([str(src)])
        manager.add_layer(ClassifierLayer("by-type", BuiltinClassifiers.extension))
        manager.scan_sources()

        start = time.time()
        manager.rebuild_indexes()
        index_time = time.time() - start

        assert index_time < 2.0  # Should complete in under 2 seconds
        print(f"\nIndex 1,000 files: {index_time:.3f}s ({1000 / index_time:.0f} files/sec)")

    def test_resolve_path_performance(self, tmp_path, benchmark_enabled):
        """Benchmark path resolution performance."""
        if not benchmark_enabled:
            pytest.skip("Benchmark tests disabled")

        src = tmp_path / "source"
        src.mkdir()
        self.create_large_filesystem(src, 1000)

        manager = LayerManager([str(src)])
        manager.add_layer(ClassifierLayer("by-type", BuiltinClassifiers.extension))
        manager.scan_sources()
        manager.rebuild_indexes()

        # Test resolution speed
        iterations = 100
        start = time.time()
        for _ in range(iterations):
            manager.resolve_path("by-type/txt/file0000.txt")
        resolve_time = time.time() - start

        avg_time = resolve_time / iterations
        assert avg_time < 0.001  # Should be under 1ms per resolution
        print(
            f"\nPath resolution: {avg_time * 1000:.3f}ms avg ({iterations / resolve_time:.0f} ops/sec)"
        )

    def test_scan_10000_files(self, tmp_path, benchmark_enabled):
        """Benchmark scanning 10,000 files (stress test)."""
        if not benchmark_enabled:
            pytest.skip("Benchmark tests disabled")

        src = tmp_path / "source"
        src.mkdir()
        self.create_large_filesystem(src, 10000)

        manager = LayerManager([str(src)])

        start = time.time()
        manager.scan_sources()
        scan_time = time.time() - start

        assert len(manager.files) == 10000
        assert scan_time < 60.0  # Should complete in under 60 seconds
        print(f"\nScan 10,000 files: {scan_time:.3f}s ({10000 / scan_time:.0f} files/sec)")

    def test_multiple_layers_performance(self, tmp_path, benchmark_enabled):
        """Benchmark with multiple layers active."""
        if not benchmark_enabled:
            pytest.skip("Benchmark tests disabled")

        src = tmp_path / "source"
        src.mkdir()
        self.create_large_filesystem(src, 1000)

        manager = LayerManager([str(src)])

        # Add three different layers
        manager.add_layer(ClassifierLayer("by-type", BuiltinClassifiers.extension))
        manager.add_layer(ClassifierLayer("by-size", BuiltinClassifiers.size))
        manager.add_layer(DateLayer("by-date", "mtime"))

        manager.scan_sources()

        start = time.time()
        manager.rebuild_indexes()
        index_time = time.time() - start

        assert index_time < 5.0  # Three layers should still be fast
        print(f"\nIndex 1,000 files × 3 layers: {index_time:.3f}s")


class TestFactoryFunctions:
    """Test factory functions for creating common layer configurations."""

    def test_create_date_layer(self, tmp_path):
        """Test LayerFactory.create_date_layer()."""
        layer = LayerFactory.create_date_layer("custom-date", "ctime")

        assert layer.name == "custom-date"
        assert isinstance(layer, DateLayer)

    def test_create_extension_layer(self, tmp_path):
        """Test LayerFactory.create_extension_layer()."""
        layer = LayerFactory.create_extension_layer("file-types")

        assert layer.name == "file-types"
        assert isinstance(layer, ClassifierLayer)

    def test_create_size_layer(self, tmp_path):
        """Test LayerFactory.create_size_layer()."""
        layer = LayerFactory.create_size_layer("files-by-size")

        assert layer.name == "files-by-size"
        assert isinstance(layer, ClassifierLayer)

    def test_create_tag_layer(self, tmp_path):
        """Test LayerFactory.create_tag_layer()."""
        layer = LayerFactory.create_tag_layer("custom-tags")

        assert layer.name == "custom-tags"
        assert isinstance(layer, TagLayer)

    def test_factory_integration(self, tmp_path):
        """Test using factory functions in real workflow."""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.py").write_text("# Test")

        manager = LayerManager([str(src)])

        # Use factory functions to create layers
        manager.add_layer(LayerFactory.create_extension_layer())
        manager.add_layer(LayerFactory.create_date_layer())
        manager.add_layer(LayerFactory.create_size_layer())

        manager.scan_sources()
        manager.rebuild_indexes()

        assert set(manager.list_directory("")) == {"by-type", "by-date", "by-size"}


# Pytest fixtures
@pytest.fixture
def benchmark_enabled(request):
    """Control whether benchmark tests run."""
    return request.config.getoption("--run-benchmarks", default=False)


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-benchmarks",
        action="store_true",
        default=False,
        help="Run performance benchmark tests",
    )
