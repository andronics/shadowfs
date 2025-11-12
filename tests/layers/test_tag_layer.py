"""
Tests for ShadowFS TagLayer.

Tests tag-based virtual layers with multiple tag sources.
Target: 90%+ coverage, 45+ tests
"""

import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from shadowfs.layers.base import FileInfo
from shadowfs.layers.tag import BuiltinExtractors, TagLayer


class TestTagLayerBasics:
    """Test TagLayer basic functionality."""

    def test_create_tag_layer_default(self):
        """Test creating a TagLayer with default extractors."""
        layer = TagLayer("by-tag")

        assert layer.name == "by-tag"
        assert len(layer.extractors) == 1  # Default xattr extractor
        assert layer.index == {}

    def test_create_tag_layer_custom_extractors(self):
        """Test creating a TagLayer with custom extractors."""

        def custom_extractor(f):
            return ["tag1"]

        layer = TagLayer("by-tag", [custom_extractor])

        assert layer.name == "by-tag"
        assert len(layer.extractors) == 1
        assert layer.extractors[0] == custom_extractor

    def test_build_index_with_empty_list(self):
        """Test building index with no files."""
        layer = TagLayer("by-tag", [])

        layer.build_index([])

        assert layer.index == {}

    def test_build_index_with_single_tag(self):
        """Test building index with file having single tag."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

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

        assert "work" in layer.index
        assert len(layer.index["work"]) == 1
        assert layer.index["work"][0].name == "test.txt"

    def test_build_index_with_multiple_tags(self):
        """Test building index with file having multiple tags."""

        def extractor(f):
            return ["work", "important"]

        layer = TagLayer("by-tag", [extractor])

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

        # File should appear in both tags
        assert "work" in layer.index
        assert "important" in layer.index
        assert len(layer.index["work"]) == 1
        assert len(layer.index["important"]) == 1
        assert layer.index["work"][0].name == "test.txt"
        assert layer.index["important"][0].name == "test.txt"

    def test_build_index_with_multiple_files_same_tag(self):
        """Test building index with multiple files sharing a tag."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

        files = [
            FileInfo(
                name=f"file{i}.txt",
                path=f"file{i}.txt",
                real_path=f"/file{i}.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
            for i in range(3)
        ]

        layer.build_index(files)

        assert "work" in layer.index
        assert len(layer.index["work"]) == 3

    def test_build_index_skips_directories(self):
        """Test that build_index skips directories."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

        files = [
            FileInfo(
                name="dir",
                path="dir",
                real_path="/dir",
                extension="",
                size=4096,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFDIR | 0o755,  # Directory
            )
        ]

        layer.build_index(files)

        assert layer.index == {}

    def test_build_index_skips_empty_tags(self):
        """Test that empty tags are skipped."""

        def extractor(f):
            return ["", "  ", "valid"]  # Empty and whitespace-only

        layer = TagLayer("by-tag", [extractor])

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

        # Only valid tag should be in index
        assert "valid" in layer.index
        assert "" not in layer.index
        assert "  " not in layer.index

    def test_build_index_handles_extractor_exceptions(self):
        """Test that build_index skips files causing extractor errors."""

        def bad_extractor(f):
            raise ValueError("Extractor error")

        layer = TagLayer("by-tag", [bad_extractor])

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

        # Should not raise exception
        layer.build_index(files)

        # File should be skipped
        assert layer.index == {}

    def test_build_index_with_multiple_extractors(self):
        """Test building index with multiple extractors."""

        def extractor1(f):
            return ["tag1"]

        def extractor2(f):
            return ["tag2"]

        layer = TagLayer("by-tag", [extractor1, extractor2])

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

        # File should have tags from both extractors
        assert "tag1" in layer.index
        assert "tag2" in layer.index

    def test_build_index_deduplicates_tags(self):
        """Test that duplicate tags from multiple extractors are deduplicated."""

        def extractor1(f):
            return ["work"]

        def extractor2(f):
            return ["work"]  # Same tag

        layer = TagLayer("by-tag", [extractor1, extractor2])

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

        # File should only appear once in the "work" tag
        assert "work" in layer.index
        assert len(layer.index["work"]) == 1

    def test_build_index_clears_existing_index(self):
        """Test that build_index clears previous index."""

        def extractor(f):
            return ["tag1"]

        layer = TagLayer("by-tag", [extractor])

        # Build first index
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
        assert "tag1" in layer.index

        # Change extractor
        layer.extractors = [lambda f: ["tag2"]]

        # Build second index
        files2 = [
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files2)

        # Old tag should be gone
        assert "tag1" not in layer.index
        assert "tag2" in layer.index


class TestTagLayerResolve:
    """Test TagLayer path resolution."""

    def test_resolve_existing_file(self):
        """Test resolving an existing file."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

        files = [
            FileInfo(
                name="test.txt",
                path="test.txt",
                real_path="/source/test.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        result = layer.resolve("work/test.txt")

        assert result == "/source/test.txt"

    def test_resolve_nonexistent_file(self):
        """Test resolving a file that doesn't exist."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

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

        result = layer.resolve("work/nonexistent.txt")

        assert result is None

    def test_resolve_nonexistent_tag(self):
        """Test resolving with a tag that doesn't exist."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

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

        result = layer.resolve("nonexistent_tag/test.txt")

        assert result is None

    def test_resolve_invalid_path_format(self):
        """Test resolving with invalid path format."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

        files: list[FileInfo] = []
        layer.build_index(files)

        # Just tag, no filename
        result = layer.resolve("work")
        assert result is None

        # Too many slashes
        result = layer.resolve("work/subdir/file.txt")
        assert result is None


class TestTagLayerListDirectory:
    """Test TagLayer directory listing."""

    def test_list_directory_root(self):
        """Test listing tags at root."""

        def extractor(f):
            if f.name == "file1.txt":
                return ["work"]
            else:
                return ["personal"]

        layer = TagLayer("by-tag", [extractor])

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
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("")

        assert result == ["personal", "work"]  # Sorted

    def test_list_directory_tag(self):
        """Test listing files in a tag."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

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
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("work")

        assert result == ["file1.txt", "file2.txt"]  # Sorted

    def test_list_directory_nonexistent_tag(self):
        """Test listing a tag that doesn't exist."""

        def extractor(f):
            return ["work"]

        layer = TagLayer("by-tag", [extractor])

        files: list[FileInfo] = []
        layer.build_index(files)

        result = layer.list_directory("nonexistent")

        assert result == []

    def test_list_directory_empty_index(self):
        """Test listing with empty index."""
        layer = TagLayer("by-tag", [])

        layer.build_index([])

        result = layer.list_directory("")

        assert result == []


class TestBuiltinExtractorXattr:
    """Test xattr extractor."""

    def test_xattr_extractor_success(self):
        """Test successful xattr extraction."""
        # Mock xattr module
        mock_xattr = MagicMock()
        mock_xattr.getxattr.return_value = b"work,important"

        with patch.dict("sys.modules", {"xattr": mock_xattr}):
            extractor = BuiltinExtractors.xattr("user.tags")

            file_info = FileInfo(
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

            result = extractor(file_info)

            assert result == ["work", "important"]
            mock_xattr.getxattr.assert_called_once_with("/test.txt", "user.tags")

    def test_xattr_extractor_whitespace(self):
        """Test xattr extraction with whitespace."""
        mock_xattr = MagicMock()
        mock_xattr.getxattr.return_value = b" work , important , "

        with patch.dict("sys.modules", {"xattr": mock_xattr}):
            extractor = BuiltinExtractors.xattr()

            file_info = FileInfo(
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

            result = extractor(file_info)

            assert result == ["work", "important"]  # Whitespace stripped

    def test_xattr_extractor_no_attribute(self):
        """Test xattr extraction when attribute doesn't exist."""
        mock_xattr = MagicMock()
        mock_xattr.getxattr.side_effect = KeyError()

        with patch.dict("sys.modules", {"xattr": mock_xattr}):
            extractor = BuiltinExtractors.xattr()

            file_info = FileInfo(
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

            result = extractor(file_info)

            assert result == []

    def test_xattr_extractor_module_not_available(self):
        """Test xattr extraction when xattr module is not available."""
        with patch.dict("sys.modules", {"xattr": None}):
            extractor = BuiltinExtractors.xattr()

            file_info = FileInfo(
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

            result = extractor(file_info)

            assert result == []


class TestBuiltinExtractorSidecar:
    """Test sidecar file extractor."""

    def test_sidecar_extractor_json_format(self):
        """Test sidecar extraction with JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file and sidecar
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            sidecar_file = Path(tmpdir) / "test.txt.tags"
            sidecar_file.write_text('["work", "important"]')

            extractor = BuiltinExtractors.sidecar(".tags")

            file_info = FileInfo(
                name="test.txt",
                path="test.txt",
                real_path=str(test_file),
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )

            result = extractor(file_info)

            assert result == ["work", "important"]

    def test_sidecar_extractor_comma_separated(self):
        """Test sidecar extraction with comma-separated format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            sidecar_file = Path(tmpdir) / "test.txt.tags"
            sidecar_file.write_text("work, important")

            extractor = BuiltinExtractors.sidecar(".tags")

            file_info = FileInfo(
                name="test.txt",
                path="test.txt",
                real_path=str(test_file),
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )

            result = extractor(file_info)

            assert result == ["work", "important"]

    def test_sidecar_extractor_no_sidecar(self):
        """Test sidecar extraction when sidecar doesn't exist."""
        extractor = BuiltinExtractors.sidecar(".tags")

        file_info = FileInfo(
            name="test.txt",
            path="test.txt",
            real_path="/nonexistent/test.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert result == []

    def test_sidecar_extractor_invalid_json(self):
        """Test sidecar extraction with invalid JSON that starts with [."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            sidecar_file = Path(tmpdir) / "test.txt.tags"
            sidecar_file.write_text("[invalid json")

            extractor = BuiltinExtractors.sidecar(".tags")

            file_info = FileInfo(
                name="test.txt",
                path="test.txt",
                real_path=str(test_file),
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )

            result = extractor(file_info)

            # Should fall back to CSV parsing
            assert result == ["[invalid json"]


class TestBuiltinExtractorFilenamePattern:
    """Test filename pattern extractor."""

    def test_filename_pattern_extractor(self):
        """Test filename pattern extraction."""
        patterns = {"test_*.py": "tests", "*.md": "docs"}
        extractor = BuiltinExtractors.filename_pattern(patterns)

        file_info = FileInfo(
            name="test_example.py",
            path="test_example.py",
            real_path="/test_example.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert "tests" in result

    def test_filename_pattern_extractor_no_match(self):
        """Test filename pattern extraction with no matches."""
        patterns = {"test_*.py": "tests"}
        extractor = BuiltinExtractors.filename_pattern(patterns)

        file_info = FileInfo(
            name="example.py",
            path="example.py",
            real_path="/example.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert result == []


class TestBuiltinExtractorPathPattern:
    """Test path pattern extractor."""

    def test_path_pattern_extractor(self):
        """Test path pattern extraction."""
        patterns = {"src/**/*.py": "source", "tests/**": "tests"}
        extractor = BuiltinExtractors.path_pattern(patterns)

        file_info = FileInfo(
            name="example.py",
            path="src/module/example.py",
            real_path="/source/src/module/example.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert "source" in result

    def test_path_pattern_extractor_no_match(self):
        """Test path pattern extraction with no matches."""
        patterns = {"src/**/*.py": "source"}
        extractor = BuiltinExtractors.path_pattern(patterns)

        file_info = FileInfo(
            name="example.py",
            path="lib/example.py",
            real_path="/lib/example.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert result == []


class TestBuiltinExtractorExtensionMap:
    """Test extension map extractor."""

    def test_extension_map_extractor(self):
        """Test extension map extraction."""
        ext_tags = {".py": ["code", "python"], ".md": ["docs"]}
        extractor = BuiltinExtractors.extension_map(ext_tags)

        file_info = FileInfo(
            name="example.py",
            path="example.py",
            real_path="/example.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert result == ["code", "python"]

    def test_extension_map_extractor_no_match(self):
        """Test extension map extraction with no matches."""
        ext_tags = {".py": ["code"]}
        extractor = BuiltinExtractors.extension_map(ext_tags)

        file_info = FileInfo(
            name="example.txt",
            path="example.txt",
            real_path="/example.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = extractor(file_info)

        assert result == []


class TestTagLayerEdgeCases:
    """Test TagLayer edge cases."""

    def test_refresh_rebuilds_index(self):
        """Test that refresh() rebuilds the index."""

        def extractor(f):
            return ["tag1"]

        layer = TagLayer("by-tag", [extractor])

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
        assert "tag1" in layer.index

        # Change extractor
        layer.extractors = [lambda f: ["tag2"]]

        # Refresh with new files
        files2 = [
            FileInfo(
                name="file2.txt",
                path="file2.txt",
                real_path="/file2.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.refresh(files2)

        # Old tag should be gone, new tag present
        assert "tag1" not in layer.index
        assert "tag2" in layer.index

    def test_repr(self):
        """Test string representation."""
        layer = TagLayer("by-tag")

        result = repr(layer)

        assert "TagLayer" in result
        assert "by-tag" in result

    def test_non_string_tags_filtered(self):
        """Test that non-string tags are filtered out."""

        def extractor(f):
            return ["valid", 123, None, "another"]  # Mixed types

        layer = TagLayer("by-tag", [extractor])

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

        # Only string tags should be in index
        assert "valid" in layer.index
        assert "another" in layer.index
        assert 123 not in layer.index  # type: ignore[comparison-overlap]
        assert None not in layer.index  # type: ignore[comparison-overlap]

    def test_sidecar_json_decode_error(self, tmp_path):
        """Test sidecar extractor when JSON parsing fails."""
        src = tmp_path / "source"
        src.mkdir()

        file_path = src / "test.txt"
        file_path.write_text("content")

        # Create sidecar file with invalid JSON that starts with "["
        sidecar_path = src / "test.txt.tags"
        sidecar_path.write_text("[invalid, json, syntax")  # Starts with [ but invalid JSON

        extractor = BuiltinExtractors.sidecar(".tags")
        file_info = FileInfo.from_path(str(file_path), str(src))

        tags = extractor(file_info)

        # Should fall back to comma-separated parsing
        # Content is "[invalid, json, syntax"
        # Split by comma gives: ["[invalid", " json", " syntax"]
        # After stripping: ["[invalid", "json", "syntax"]
        assert "json" in tags
        assert "syntax" in tags

    def test_sidecar_json_parses_but_not_list(self, tmp_path, monkeypatch):
        """Test sidecar when JSON parses successfully but isn't a list."""
        src = tmp_path / "source"
        src.mkdir()

        file_path = src / "test.txt"
        file_path.write_text("content")

        # Create sidecar file with content starting with "["
        sidecar_path = src / "test.txt.tags"
        sidecar_path.write_text("[tag1, tag2, tag3")  # Will be parsed as comma-separated

        # Mock json.loads to return a dict instead of a list
        # This tests the branch where isinstance(tags, list) is False (line 233->239)
        import json

        original_loads = json.loads

        def mock_loads(s):
            if s.startswith("["):
                # Return a dict instead of a list to trigger the False branch
                return {"not": "a list"}
            return original_loads(s)

        monkeypatch.setattr(json, "loads", mock_loads)

        extractor = BuiltinExtractors.sidecar(".tags")
        file_info = FileInfo.from_path(str(file_path), str(src))

        tags = extractor(file_info)

        # Should fall back to comma-separated parsing since isinstance(tags, list) is False
        # Content: "[tag1, tag2, tag3"
        # Split by comma and strip: ["[tag1", "tag2", "tag3"]
        assert "tag2" in tags
        assert "tag3" in tags
