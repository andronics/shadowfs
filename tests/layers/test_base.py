"""
Tests for ShadowFS Virtual Layers Base Classes.

Tests FileInfo dataclass and Layer abstract base class.
Target: 95%+ coverage
"""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from shadowfs.layers.base import FileInfo, Layer


class TestFileInfo:
    """Test FileInfo dataclass."""

    def test_create_fileinfo_with_all_fields(self):
        """Can create FileInfo with all required fields."""
        info = FileInfo(
            name="test.py",
            path="src/test.py",
            real_path="/source/src/test.py",
            extension=".py",
            size=1024,
            mtime=1000000.0,
            ctime=2000000.0,
            atime=3000000.0,
            mode=stat.S_IFREG | 0o644,
        )

        assert info.name == "test.py"
        assert info.path == "src/test.py"
        assert info.real_path == "/source/src/test.py"
        assert info.extension == ".py"
        assert info.size == 1024
        assert info.mtime == 1000000.0
        assert info.ctime == 2000000.0
        assert info.atime == 3000000.0
        assert info.mode == stat.S_IFREG | 0o644

    def test_fileinfo_is_immutable(self):
        """Test FileInfo should be immutable (frozen dataclass)."""
        info = FileInfo(
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

        with pytest.raises(AttributeError):
            info.name = "changed.py"

        with pytest.raises(AttributeError):
            info.size = 200

    def test_from_path_creates_fileinfo(self, temp_dir):
        """Test from_path() creates FileInfo from a real file."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World")

        # Create FileInfo
        info = FileInfo.from_path(str(test_file))

        assert info.name == "test.txt"
        assert info.extension == ".txt"
        assert info.size == 11  # "Hello World" is 11 bytes
        assert info.real_path == str(test_file.absolute())
        assert info.mtime > 0
        assert info.ctime > 0
        assert info.atime > 0

    def test_from_path_with_source_root(self, temp_dir):
        """Test from_path() computes relative path from source_root."""
        # Create nested structure
        src_dir = temp_dir / "src"
        src_dir.mkdir()
        test_file = src_dir / "project.py"
        test_file.write_text("# code")

        # Create FileInfo with source root
        info = FileInfo.from_path(str(test_file), source_root=str(temp_dir))

        assert info.name == "project.py"
        assert info.path == os.path.join("src", "project.py")
        assert info.real_path == str(test_file.absolute())

    def test_from_path_without_source_root(self, temp_dir):
        """Test from_path() uses filename as path when no source_root."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        info = FileInfo.from_path(str(test_file))

        assert info.name == "test.txt"
        assert info.path == "test.txt"  # Just the filename

    def test_from_path_nonexistent_file(self):
        """Test from_path() raises FileNotFoundError for nonexistent files."""
        with pytest.raises(FileNotFoundError):
            FileInfo.from_path("/nonexistent/file.txt")

    def test_extension_with_multiple_dots(self, temp_dir):
        """Test extension extraction handles files with multiple dots."""
        test_file = temp_dir / "archive.tar.gz"
        test_file.write_text("data")

        info = FileInfo.from_path(str(test_file))

        assert info.name == "archive.tar.gz"
        assert info.extension == ".gz"  # os.path.splitext returns last extension

    def test_extension_no_extension(self, temp_dir):
        """Test files without extension have empty extension string."""
        test_file = temp_dir / "README"
        test_file.write_text("docs")

        info = FileInfo.from_path(str(test_file))

        assert info.name == "README"
        assert info.extension == ""

    def test_extension_hidden_file(self, temp_dir):
        """Test hidden files (starting with dot) handled correctly."""
        test_file = temp_dir / ".gitignore"
        test_file.write_text("*.pyc")

        info = FileInfo.from_path(str(test_file))

        assert info.name == ".gitignore"
        assert info.extension == ""  # No extension

    def test_extension_hidden_file_with_extension(self, temp_dir):
        """Test hidden files with extension handled correctly."""
        test_file = temp_dir / ".env.local"
        test_file.write_text("API_KEY=secret")

        info = FileInfo.from_path(str(test_file))

        assert info.name == ".env.local"
        assert info.extension == ".local"

    def test_is_file_property_for_regular_file(self, temp_dir):
        """Test is_file property returns True for regular files."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        info = FileInfo.from_path(str(test_file))

        assert info.is_file is True
        assert info.is_dir is False
        assert info.is_symlink is False

    def test_is_dir_property_for_directory(self, temp_dir):
        """Test is_dir property returns True for directories."""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        info = FileInfo.from_path(str(test_dir))

        assert info.is_dir is True
        assert info.is_file is False
        assert info.is_symlink is False

    def test_fileinfo_with_zero_size_file(self, temp_dir):
        """Test FileInfo handles zero-size files correctly."""
        empty_file = temp_dir / "empty.txt"
        empty_file.touch()

        info = FileInfo.from_path(str(empty_file))

        assert info.size == 0
        assert info.is_file is True

    def test_fileinfo_with_large_file(self, temp_dir):
        """Test FileInfo handles large files correctly."""
        large_file = temp_dir / "large.bin"
        large_file.write_bytes(b"x" * (1024 * 1024))  # 1MB

        info = FileInfo.from_path(str(large_file))

        assert info.size == 1024 * 1024

    def test_fileinfo_preserves_timestamps(self, temp_dir):
        """Test FileInfo preserves file timestamps accurately."""
        test_file = temp_dir / "timestamped.txt"
        test_file.write_text("data")

        # Get original timestamps
        original_stat = os.stat(test_file)

        info = FileInfo.from_path(str(test_file))

        # Timestamps should match (within floating point precision)
        assert abs(info.mtime - original_stat.st_mtime) < 0.001
        assert abs(info.ctime - original_stat.st_ctime) < 0.001
        assert abs(info.atime - original_stat.st_atime) < 0.001

    def test_fileinfo_real_path_is_absolute(self, temp_dir):
        """Test FileInfo.real_path is always absolute, even if input is relative."""
        # Change to temp dir
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            test_file = Path("relative.txt")
            test_file.write_text("content")

            # Create with relative path
            info = FileInfo.from_path("relative.txt")

            # real_path should be absolute
            assert os.path.isabs(info.real_path)
            assert info.real_path.endswith("relative.txt")
        finally:
            os.chdir(original_cwd)

    def test_fileinfo_mode_preserves_permissions(self, temp_dir):
        """Test FileInfo preserves file permissions in mode."""
        test_file = temp_dir / "executable.sh"
        test_file.write_text("#!/bin/bash\necho test")
        test_file.chmod(0o755)

        info = FileInfo.from_path(str(test_file))

        # Check that execute bit is set
        assert info.mode & stat.S_IXUSR
        assert info.is_file is True


class TestVirtualLayer:
    """Test Layer abstract base class."""

    def test_virtual_layer_is_abstract(self):
        """Layer cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            Layer("test")

        assert "abstract" in str(exc_info.value).lower()

    def test_virtual_layer_requires_build_index(self):
        """Subclass must implement build_index()."""

        class IncompleteLayer(Layer):
            def resolve(self, virtual_path):
                return None

            def list_directory(self, subpath=""):
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteLayer("test")

        assert "build_index" in str(exc_info.value) or "abstract" in str(exc_info.value).lower()

    def test_virtual_layer_requires_resolve(self):
        """Subclass must implement resolve()."""

        class IncompleteLayer(Layer):
            def build_index(self, files):
                pass

            def list_directory(self, subpath=""):
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteLayer("test")

        assert "resolve" in str(exc_info.value) or "abstract" in str(exc_info.value).lower()

    def test_virtual_layer_requires_list_directory(self):
        """Subclass must implement list_directory()."""

        class IncompleteLayer(Layer):
            def build_index(self, files):
                pass

            def resolve(self, virtual_path):
                return None

        with pytest.raises(TypeError) as exc_info:
            IncompleteLayer("test")

        assert "list_directory" in str(exc_info.value) or "abstract" in str(exc_info.value).lower()

    def test_concrete_layer_can_be_instantiated(self):
        """Concrete implementation with all methods can be instantiated."""

        class ConcreteLayer(Layer):
            def build_index(self, files):
                self.files = files

            def resolve(self, virtual_path):
                return f"/real/{virtual_path}"

            def list_directory(self, subpath=""):
                return ["file1", "file2"]

        layer = ConcreteLayer("test-layer")

        assert layer.name == "test-layer"
        assert isinstance(layer, Layer)

    def test_virtual_layer_stores_name(self):
        """Layer stores the layer name."""

        class ConcreteLayer(Layer):
            def build_index(self, files):
                pass

            def resolve(self, virtual_path):
                return None

            def list_directory(self, subpath=""):
                return []

        layer = ConcreteLayer("my-layer")

        assert layer.name == "my-layer"

    def test_default_refresh_calls_build_index(self):
        """Default refresh() implementation rebuilds the index."""

        class ConcreteLayer(Layer):
            def __init__(self, name):
                super().__init__(name)
                self.build_count = 0

            def build_index(self, files):
                self.build_count += 1
                self.files = files

            def resolve(self, virtual_path):
                return None

            def list_directory(self, subpath=""):
                return []

        layer = ConcreteLayer("test")
        files = [
            FileInfo(
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
        ]

        # Initial build
        layer.build_index(files)
        assert layer.build_count == 1

        # Refresh should call build_index again
        layer.refresh(files)
        assert layer.build_count == 2

    def test_virtual_layer_repr(self):
        """Layer has useful string representation."""

        class ConcreteLayer(Layer):
            def build_index(self, files):
                pass

            def resolve(self, virtual_path):
                return None

            def list_directory(self, subpath=""):
                return []

        layer = ConcreteLayer("my-layer")
        repr_str = repr(layer)

        assert "ConcreteLayer" in repr_str
        assert "my-layer" in repr_str

    def test_refresh_can_be_overridden(self):
        """Subclass can override refresh() for incremental updates."""

        class IncrementalLayer(Layer):
            def __init__(self, name):
                super().__init__(name)
                self.refresh_count = 0

            def build_index(self, files):
                self.files = files

            def resolve(self, virtual_path):
                return None

            def list_directory(self, subpath=""):
                return []

            def refresh(self, files):
                # Custom refresh logic
                self.refresh_count += 1

        layer = IncrementalLayer("test")
        layer.refresh([])

        assert layer.refresh_count == 1


class TestFileInfoEdgeCases:
    """Test edge cases and error conditions for FileInfo."""

    def test_fileinfo_with_unicode_filename(self, temp_dir):
        """Test FileInfo handles Unicode filenames correctly."""
        unicode_file = temp_dir / "文件.txt"
        unicode_file.write_text("content")

        info = FileInfo.from_path(str(unicode_file))

        assert info.name == "文件.txt"
        assert info.extension == ".txt"

    def test_fileinfo_with_spaces_in_name(self, temp_dir):
        """Test FileInfo handles spaces in filenames."""
        spaced_file = temp_dir / "my file.txt"
        spaced_file.write_text("content")

        info = FileInfo.from_path(str(spaced_file))

        assert info.name == "my file.txt"
        assert info.extension == ".txt"

    def test_fileinfo_with_special_characters(self, temp_dir):
        """Test FileInfo handles special characters in filenames."""
        special_file = temp_dir / "file@#$%.txt"
        special_file.write_text("content")

        info = FileInfo.from_path(str(special_file))

        assert info.name == "file@#$%.txt"
        assert info.extension == ".txt"

    def test_fileinfo_equality(self):
        """Two FileInfo instances with same data are equal."""
        info1 = FileInfo(
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

        info2 = FileInfo(
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

        assert info1 == info2

    def test_fileinfo_hash(self):
        """Test FileInfo instances are hashable (frozen=True)."""
        info = FileInfo(
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

        # Should be able to use in sets and as dict keys
        file_set = {info}
        assert info in file_set

        file_dict = {info: "metadata"}
        assert file_dict[info] == "metadata"

    def test_fileinfo_from_path_windows_different_drives(self, temp_dir, monkeypatch):
        """Test FileInfo.from_path when paths are on different drives (Windows)."""
        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        # Mock os.path.relpath to raise ValueError (simulates different drives on Windows)
        original_relpath = os.path.relpath

        def mock_relpath(path, start):
            raise ValueError("path is on mount 'C:', start on mount 'D:'")

        monkeypatch.setattr(os.path, "relpath", mock_relpath)

        # Should fall back to using real_path as path
        info = FileInfo.from_path(str(test_file), str(temp_dir))
        assert info.path == str(test_file)
        assert info.name == "test.txt"

        # Restore
        monkeypatch.setattr(os.path, "relpath", original_relpath)

    def test_abstract_methods_coverage(self):
        """Test abstract method pass statements for coverage."""

        # Create a concrete implementation that explicitly calls the abstract methods
        # via super() to execute the pass statements
        class CoverageTestLayer(Layer):
            """Test layer that calls abstract method implementations."""

            def build_index(self, files):
                # Call the abstract method implementation to cover line 154
                super().build_index(files)
                self.index = {}

            def resolve(self, virtual_path):
                # Call the abstract method implementation to cover line 169
                super().resolve(virtual_path)
                return None

            def list_directory(self, subpath=""):
                # Call the abstract method implementation to cover line 185
                super().list_directory(subpath)
                return []

        layer = CoverageTestLayer("test")

        # Exercise all abstract methods to cover the pass statements
        layer.build_index([])
        layer.resolve("test/path")
        layer.list_directory("test")


# Fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
