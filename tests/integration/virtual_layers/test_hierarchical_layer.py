"""
Tests for ShadowFS HierarchicalLayer.

Tests hierarchical multi-level virtual layers with classifier chains.
Target: 90%+ coverage, 50+ tests
"""

import stat

from shadowfs.integration.virtual_layers.base import FileInfo
from shadowfs.integration.virtual_layers.hierarchical_layer import (
    BuiltinClassifiers,
    HierarchicalLayer,
)


class TestHierarchicalLayerBasics:
    """Test HierarchicalLayer basic functionality."""

    def test_create_hierarchical_layer(self):
        """Test creating a hierarchical layer with classifiers."""

        def level1(f):
            return "cat1"

        def level2(f):
            return "cat2"

        layer = HierarchicalLayer("by-hierarchy", [level1, level2])

        assert layer.name == "by-hierarchy"
        assert len(layer.classifiers) == 2
        assert layer.index == {}

    def test_create_with_empty_classifiers_raises(self):
        """Test that empty classifiers list raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="Classifiers list cannot be empty"):
            HierarchicalLayer("test", [])

    def test_build_index_single_level(self):
        """Test building index with single-level hierarchy."""

        def classifier(f):
            return "category"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert "category" in layer.index
        assert "__files__" in layer.index["category"]
        assert len(layer.index["category"]["__files__"]) == 1

    def test_build_index_two_levels(self):
        """Test building index with two-level hierarchy."""

        def level1(f):
            return "cat1"

        def level2(f):
            return "cat2"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert "cat1" in layer.index
        assert "cat2" in layer.index["cat1"]
        assert "__files__" in layer.index["cat1"]["cat2"]
        assert len(layer.index["cat1"]["cat2"]["__files__"]) == 1

    def test_build_index_three_levels(self):
        """Test building index with three-level hierarchy."""

        def level1(f):
            return "L1"

        def level2(f):
            return "L2"

        def level3(f):
            return "L3"

        layer = HierarchicalLayer("by-test", [level1, level2, level3])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert "L1" in layer.index
        assert "L2" in layer.index["L1"]
        assert "L3" in layer.index["L1"]["L2"]
        assert "__files__" in layer.index["L1"]["L2"]["L3"]

    def test_build_index_multiple_files_same_categories(self):
        """Test multiple files with same classification."""

        def classifier(f):
            return "same"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert len(layer.index["same"]["__files__"]) == 2

    def test_build_index_different_categories(self):
        """Test files with different classifications."""

        def classifier(f):
            # Classify by size
            return "small" if f.size < 150 else "large"

        layer = HierarchicalLayer("by-size", [classifier])

        files = [
            FileInfo(
                name="small.txt",
                path="small.txt",
                real_path="/small.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="large.txt",
                path="large.txt",
                real_path="/large.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "small" in layer.index
        assert "large" in layer.index
        assert len(layer.index["small"]["__files__"]) == 1
        assert len(layer.index["large"]["__files__"]) == 1

    def test_build_index_skips_directories(self):
        """Test that directories are skipped during indexing."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="dir",
                path="dir",
                real_path="/dir",
                extension="",
                size=0,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFDIR | 0o755,  # Directory
            )
        ]

        layer.build_index(files)

        assert layer.index == {}

    def test_build_index_skips_files_with_empty_category(self):
        """Test that files returning empty categories are skipped."""

        def classifier(f):
            return ""  # Empty category

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert layer.index == {}

    def test_build_index_skips_files_with_none_category(self):
        """Test that files returning None categories are skipped."""

        def classifier(f):
            return None

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        assert layer.index == {}

    def test_build_index_handles_classifier_exception(self):
        """Test graceful handling of classifier exceptions."""

        def failing_classifier(f):
            raise RuntimeError("Classifier error")

        layer = HierarchicalLayer("by-test", [failing_classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # File should be skipped
        assert layer.index == {}

    def test_build_index_partial_classification(self):
        """Test files where only some classifiers succeed."""

        def level1(f):
            return "cat1"

        def level2(f):
            return ""  # Empty - should skip file

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # File should be skipped (didn't complete all levels)
        assert layer.index == {}

    def test_refresh_index_clears_previous(self):
        """Test that rebuilding index clears previous entries."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        # Build initial index
        files1 = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files1)

        assert len(layer.index["cat"]["__files__"]) == 1

        # Rebuild with different files
        files2 = [
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files2)

        # Should only have new file
        assert len(layer.index["cat"]["__files__"]) == 1
        assert layer.index["cat"]["__files__"][0].name == "file2.txt"


class TestPathResolution:
    """Test path resolution functionality."""

    def test_resolve_single_level(self):
        """Test resolving path with single level."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/real/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.resolve("cat/test.txt")

        assert result == "/real/test.txt"

    def test_resolve_two_levels(self):
        """Test resolving path with two levels."""

        def level1(f):
            return "L1"

        def level2(f):
            return "L2"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/real/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.resolve("L1/L2/test.txt")

        assert result == "/real/test.txt"

    def test_resolve_three_levels(self):
        """Test resolving path with three levels."""

        def level1(f):
            return "A"

        def level2(f):
            return "B"

        def level3(f):
            return "C"

        layer = HierarchicalLayer("by-test", [level1, level2, level3])

        files = [
            FileInfo(
                name="file.txt",
                path="file.txt",
                real_path="/real/file.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.resolve("A/B/C/file.txt")

        assert result == "/real/file.txt"

    def test_resolve_nonexistent_category(self):
        """Test resolving with nonexistent category."""

        def classifier(f):
            return "exists"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.resolve("nonexistent/test.txt")

        assert result is None

    def test_resolve_nonexistent_file(self):
        """Test resolving with nonexistent filename."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="exists.txt",
                path="exists.txt",
                real_path="/exists.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.resolve("cat/nonexistent.txt")

        assert result is None

    def test_resolve_incomplete_path(self):
        """Test resolving path that's too short."""

        def level1(f):
            return "L1"

        def level2(f):
            return "L2"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Missing second level
        result = layer.resolve("L1/test.txt")

        assert result is None

    def test_resolve_multiple_files_same_category(self):
        """Test resolving specific file among multiple in same category."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/real/file1.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/real/file2.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        result1 = layer.resolve("cat/file1.txt")
        result2 = layer.resolve("cat/file2.txt")

        assert result1 == "/real/file1.txt"
        assert result2 == "/real/file2.txt"


class TestDirectoryListing:
    """Test directory listing functionality."""

    def test_list_directory_root_single_level(self):
        """Test listing root with single level."""

        def classifier(f):
            return "cat1" if f.size < 150 else "cat2"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="small.txt",
                path="small.txt",
                real_path="/small.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="large.txt",
                path="large.txt",
                real_path="/large.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        result = layer.list_directory("")

        assert result == ["cat1", "cat2"]

    def test_list_directory_root_two_levels(self):
        """Test listing root with two levels."""

        def level1(f):
            return "A" if f.size < 150 else "B"

        def level2(f):
            return "X"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        result = layer.list_directory("")

        assert result == ["A", "B"]

    def test_list_directory_first_level(self):
        """Test listing first level subdirectory."""

        def level1(f):
            return "cat"

        def level2(f):
            return "subA" if f.size < 150 else "subB"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="small.txt",
                path="small.txt",
                real_path="/small.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="large.txt",
                path="large.txt",
                real_path="/large.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        result = layer.list_directory("cat")

        assert result == ["subA", "subB"]

    def test_list_directory_leaf_level_lists_files(self):
        """Test listing at leaf level returns files."""

        def level1(f):
            return "cat"

        def level2(f):
            return "sub"

        layer = HierarchicalLayer("by-test", [level1, level2])

        files = [
            FileInfo(
                name="file1.txt",
                path="file1.txt",
                real_path="/file1.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        result = layer.list_directory("cat/sub")

        assert result == ["file1.txt", "file2.txt"]

    def test_list_directory_nonexistent_returns_empty(self):
        """Test listing nonexistent directory returns empty list."""

        def classifier(f):
            return "exists"

        layer = HierarchicalLayer("by-test", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        result = layer.list_directory("nonexistent")

        assert result == []

    def test_list_directory_empty_index(self):
        """Test listing with empty index."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("by-test", [classifier])

        layer.build_index([])

        result = layer.list_directory("")

        assert result == []

    def test_list_directory_three_levels(self):
        """Test listing at various levels in 3-level hierarchy."""

        def level1(f):
            return "L1"

        def level2(f):
            return "L2"

        def level3(f):
            return "L3"

        layer = HierarchicalLayer("by-test", [level1, level2, level3])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Test each level
        assert layer.list_directory("") == ["L1"]
        assert layer.list_directory("L1") == ["L2"]
        assert layer.list_directory("L1/L2") == ["L3"]
        assert layer.list_directory("L1/L2/L3") == ["test.txt"]


class TestBuiltinClassifiers:
    """Test built-in classifier factories."""

    def test_by_path_component_first(self):
        """Test by_path_component with first component."""
        classifier = BuiltinClassifiers.by_path_component(0)

        file_info = FileInfo(
            name="file.txt",
            path="project/src/file.txt",
            real_path="/real/project/src/file.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "project"

    def test_by_path_component_second(self):
        """Test by_path_component with second component."""
        classifier = BuiltinClassifiers.by_path_component(1)

        file_info = FileInfo(
            name="file.txt",
            path="project/src/file.txt",
            real_path="/real/project/src/file.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "src"

    def test_by_path_component_out_of_bounds(self):
        """Test by_path_component with out of bounds index."""
        classifier = BuiltinClassifiers.by_path_component(10)

        file_info = FileInfo(
            name="file.txt",
            path="project/src/file.txt",
            real_path="/real/file.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == ""

    def test_by_path_component_in_hierarchy(self):
        """Test using by_path_component in actual hierarchy."""
        project_classifier = BuiltinClassifiers.by_path_component(0)
        subdir_classifier = BuiltinClassifiers.by_path_component(1)

        layer = HierarchicalLayer("by-project", [project_classifier, subdir_classifier])

        files = [
            FileInfo(
                name="main.py",
                path="projectA/src/main.py",
                real_path="/real/projectA/src/main.py",
                extension=".py",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="test.py",
                path="projectA/tests/test.py",
                real_path="/real/projectA/tests/test.py",
                extension=".py",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        # Verify structure
        assert "projectA" in layer.index
        assert "src" in layer.index["projectA"]
        assert "tests" in layer.index["projectA"]

        # Verify resolution
        assert layer.resolve("projectA/src/main.py") == "/real/projectA/src/main.py"
        assert layer.resolve("projectA/tests/test.py") == "/real/projectA/tests/test.py"

    def test_by_extension_group(self):
        """Test by_extension_group classifier."""
        groups = {
            "code": [".py", ".js"],
            "docs": [".md", ".txt"],
        }

        classifier = BuiltinClassifiers.by_extension_group(groups)

        py_file = FileInfo(
            name="test.py",
            path="test.py",
            real_path="/test.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        md_file = FileInfo(
            name="README.md",
            path="README.md",
            real_path="/README.md",
            extension=".md",
            size=200,
            mtime=2.0,
            ctime=2.0,
            atime=2.0,
            mode=stat.S_IFREG | 0o644,
        )

        other_file = FileInfo(
            name="data.json",
            path="data.json",
            real_path="/data.json",
            extension=".json",
            size=300,
            mtime=3.0,
            ctime=3.0,
            atime=3.0,
            mode=stat.S_IFREG | 0o644,
        )

        assert classifier(py_file) == "code"
        assert classifier(md_file) == "docs"
        assert classifier(other_file) == "other"

    def test_by_extension_group_in_hierarchy(self):
        """Test using by_extension_group in hierarchy."""
        groups = {
            "source": [".py", ".js"],
            "documentation": [".md"],
        }

        ext_classifier = BuiltinClassifiers.by_extension_group(groups)
        layer = HierarchicalLayer("by-type", [ext_classifier])

        files = [
            FileInfo(
                name="main.py",
                path="main.py",
                real_path="/main.py",
                extension=".py",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="README.md",
                path="README.md",
                real_path="/README.md",
                extension=".md",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "source" in layer.index
        assert "documentation" in layer.index

    def test_by_size_range(self):
        """Test by_size_range classifier."""
        ranges = {
            "small": (0, 1024),
            "medium": (1024, 1048576),
            "large": (1048576, float("inf")),
        }

        classifier = BuiltinClassifiers.by_size_range(ranges)

        small_file = FileInfo(
            name="small.txt",
            path="small.txt",
            real_path="/small.txt",
            extension=".txt",
            size=500,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        medium_file = FileInfo(
            name="medium.txt",
            path="medium.txt",
            real_path="/medium.txt",
            extension=".txt",
            size=50000,
            mtime=2.0,
            ctime=2.0,
            atime=2.0,
            mode=stat.S_IFREG | 0o644,
        )

        large_file = FileInfo(
            name="large.txt",
            path="large.txt",
            real_path="/large.txt",
            extension=".txt",
            size=2000000,
            mtime=3.0,
            ctime=3.0,
            atime=3.0,
            mode=stat.S_IFREG | 0o644,
        )

        assert classifier(small_file) == "small"
        assert classifier(medium_file) == "medium"
        assert classifier(large_file) == "large"

    def test_by_size_range_in_hierarchy(self):
        """Test using by_size_range in hierarchy."""
        ranges = {
            "tiny": (0, 100),
            "normal": (100, 1000),
        }

        size_classifier = BuiltinClassifiers.by_size_range(ranges)
        layer = HierarchicalLayer("by-size", [size_classifier])

        files = [
            FileInfo(
                name="tiny.txt",
                path="tiny.txt",
                real_path="/tiny.txt",
                extension=".txt",
                size=50,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="normal.txt",
                path="normal.txt",
                real_path="/normal.txt",
                extension=".txt",
                size=500,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "tiny" in layer.index
        assert "normal" in layer.index

    def test_by_size_range_unknown_category(self):
        """Test by_size_range with file outside all ranges."""
        ranges = {
            "small": (0, 100),
            "medium": (100, 200),
        }

        classifier = BuiltinClassifiers.by_size_range(ranges)

        # File larger than all ranges
        large_file = FileInfo(
            name="huge.txt",
            path="huge.txt",
            real_path="/huge.txt",
            extension=".txt",
            size=1000,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(large_file)

        assert result == "unknown"


class TestComplexHierarchies:
    """Test complex multi-level hierarchies."""

    def test_project_type_hierarchy(self):
        """Test project/type 2-level hierarchy."""
        # Project by first path component, type by extension
        project_classifier = BuiltinClassifiers.by_path_component(0)
        type_groups = {
            "source": [".py", ".js"],
            "tests": [".test.py"],
            "docs": [".md"],
        }
        type_classifier = BuiltinClassifiers.by_extension_group(type_groups)

        layer = HierarchicalLayer("by-project", [project_classifier, type_classifier])

        files = [
            FileInfo(
                name="main.py",
                path="projectA/main.py",
                real_path="/projectA/main.py",
                extension=".py",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
            FileInfo(
                name="README.md",
                path="projectA/README.md",
                real_path="/projectA/README.md",
                extension=".md",
                size=200,
                mtime=2.0,
                ctime=2.0,
                atime=2.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        # Verify structure
        assert layer.list_directory("") == ["projectA"]
        assert sorted(layer.list_directory("projectA")) == ["docs", "source"]
        assert layer.list_directory("projectA/source") == ["main.py"]
        assert layer.list_directory("projectA/docs") == ["README.md"]

    def test_four_level_hierarchy(self):
        """Test 4-level deep hierarchy."""

        def level1(f):
            return "A"

        def level2(f):
            return "B"

        def level3(f):
            return "C"

        def level4(f):
            return "D"

        layer = HierarchicalLayer("deep", [level1, level2, level3, level4])

        files = [
            FileInfo(
                name="file.txt",
                path="file.txt",
                real_path="/file.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Navigate all 4 levels
        assert layer.list_directory("") == ["A"]
        assert layer.list_directory("A") == ["B"]
        assert layer.list_directory("A/B") == ["C"]
        assert layer.list_directory("A/B/C") == ["D"]
        assert layer.list_directory("A/B/C/D") == ["file.txt"]
        assert layer.resolve("A/B/C/D/file.txt") == "/file.txt"

    def test_corrupted_index_structure(self):
        """Test defensive checks for corrupted index structure."""

        def classifier(f):
            return "cat"

        layer = HierarchicalLayer("layer", [classifier])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # Manually corrupt the index to test defensive checks
        # Replace the category dict with a non-dict value (e.g., a list)
        # This triggers the isinstance(current, dict) check in list_directory
        layer.index["cat"] = ["corrupted_value"]  # Not a dict

        # list_directory should handle this gracefully
        result = layer.list_directory("cat")
        assert result == []  # Should return empty list when current is not a dict

        # Rebuild for next test
        layer.build_index(files)

        # Corrupt differently for _get_files_at_path
        layer.index["cat"] = "string_instead_of_dict"

        # _get_files_at_path should also handle this
        result = layer._get_files_at_path(["cat"])
        assert result is None  # Returns None when path doesn't exist properly

    def test_classifiers_all_return_empty(self):
        """Test when all classifiers succeed but return empty strings."""

        def classifier_returns_empty(f):
            return ""  # Returns empty string (not None)

        layer = HierarchicalLayer("layer", [classifier_returns_empty])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        layer.build_index(files)

        # The file should not be indexed because all categories are empty
        # This triggers the `if categories:` check (line 116)
        assert layer.index == {}  # No files indexed
        assert layer.list_directory("") == []

    def test_empty_categories_after_for_loop_completion(self):
        """Test branch when for loop completes but categories is empty."""

        def dummy_classifier(f):
            return "cat"

        layer = HierarchicalLayer("layer", [dummy_classifier])

        # Create file list
        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]

        # Bypass the __init__ validation by directly setting classifiers to empty
        # This forces the for-else block to execute with empty categories
        layer.classifiers = []
        layer.build_index(files)

        # With empty classifiers, the for loop completes immediately
        # categories = [] (empty)
        # The else clause executes
        # `if categories:` on line 116 is False
        # We skip _add_to_index and continue to next file (branch 116->100)
        assert layer.index == {}  # No files indexed because categories was empty
        assert layer.list_directory("") == []
