"""
Tests for ShadowFS ClassifierLayer.

Tests classification-based virtual layers and built-in classifiers.
Target: 90%+ coverage, 50+ tests
"""

import stat
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.integration.virtual_layers.base import FileInfo
from shadowfs.integration.virtual_layers.classifier_layer import BuiltinClassifiers, ClassifierLayer


class TestClassifierLayerBasics:
    """Test ClassifierLayer basic functionality."""

    def test_create_classifier_layer(self):
        """Test creating a ClassifierLayer instance."""

        def classifier(f):
            return f.extension.lstrip(".")

        layer = ClassifierLayer("by-extension", classifier)

        assert layer.name == "by-extension"
        assert layer.classifier == classifier
        assert layer.index == {}

    def test_build_index_with_empty_list(self):
        """Test building index with no files."""

        def classifier(f):
            return "test"

        layer = ClassifierLayer("test", classifier)

        layer.build_index([])

        assert layer.index == {}

    def test_build_index_with_single_file(self):
        """Test building index with one file."""

        def classifier(f):
            return "category1"

        layer = ClassifierLayer("test", classifier)

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

        assert "category1" in layer.index
        assert len(layer.index["category1"]) == 1
        assert layer.index["category1"][0].name == "test.txt"

    def test_build_index_with_multiple_files_same_category(self):
        """Test building index with multiple files in same category."""

        def classifier(f):
            return "same"

        layer = ClassifierLayer("test", classifier)

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

        assert "same" in layer.index
        assert len(layer.index["same"]) == 3

    def test_build_index_with_multiple_categories(self):
        """Test building index with files in different categories."""

        def classifier(f):
            return f.extension.lstrip(".")

        layer = ClassifierLayer("test", classifier)

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
            ),
            FileInfo(
                name="test.js",
                path="test.js",
                real_path="/test.js",
                extension=".js",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]

        layer.build_index(files)

        assert "py" in layer.index
        assert "js" in layer.index
        assert len(layer.index["py"]) == 1
        assert len(layer.index["js"]) == 1

    def test_build_index_skips_directories(self):
        """Test that build_index skips directories."""

        def classifier(f):
            return "test"

        layer = ClassifierLayer("test", classifier)

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

    def test_build_index_skips_empty_categories(self):
        """Test that files with empty category are skipped."""

        def classifier(f):
            return ""  # Empty category

        layer = ClassifierLayer("test", classifier)

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

    def test_build_index_handles_classifier_exceptions(self):
        """Test that build_index skips files that cause classifier errors."""

        def bad_classifier(f):
            raise ValueError("Classifier error")

        layer = ClassifierLayer("test", bad_classifier)

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

        assert layer.index == {}

    def test_build_index_clears_existing_index(self):
        """Test that build_index clears previous index."""

        def classifier(f):
            return f.extension.lstrip(".")

        layer = ClassifierLayer("test", classifier)

        # Build first index
        files1 = [
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
        layer.build_index(files1)
        assert "py" in layer.index

        # Build second index with different files
        files2 = [
            FileInfo(
                name="test.js",
                path="test.js",
                real_path="/test.js",
                extension=".js",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files2)

        # Old category should be gone
        assert "py" not in layer.index
        assert "js" in layer.index


class TestClassifierLayerResolve:
    """Test ClassifierLayer path resolution."""

    def test_resolve_existing_file(self):
        """Test resolving an existing file."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

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

        result = layer.resolve("cat1/test.txt")

        assert result == "/source/test.txt"

    def test_resolve_nonexistent_file(self):
        """Test resolving a file that doesn't exist."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

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

        result = layer.resolve("cat1/nonexistent.txt")

        assert result is None

    def test_resolve_nonexistent_category(self):
        """Test resolving with a category that doesn't exist."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

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

        result = layer.resolve("nonexistent_cat/test.txt")

        assert result is None

    def test_resolve_invalid_path_format(self):
        """Test resolving with invalid path format."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

        files = []
        layer.build_index(files)

        # Just category, no filename
        result = layer.resolve("cat1")
        assert result is None

        # Too many slashes
        result = layer.resolve("cat1/subdir/file.txt")
        assert result is None

    def test_resolve_with_subdirectories_in_filename(self):
        """Test resolving files with subdirectories in filename."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

        files = [
            FileInfo(
                name="file.txt",  # Filename only
                path="subdir/file.txt",  # Full path
                real_path="/source/subdir/file.txt",
                extension=".txt",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            )
        ]
        layer.build_index(files)

        # Resolve by filename (not full path)
        result = layer.resolve("cat1/file.txt")

        assert result == "/source/subdir/file.txt"


class TestClassifierLayerListDirectory:
    """Test ClassifierLayer directory listing."""

    def test_list_directory_root(self):
        """Test listing categories at root."""

        def classifier(f):
            return f.extension.lstrip(".")

        layer = ClassifierLayer("test", classifier)

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
            ),
            FileInfo(
                name="test.js",
                path="test.js",
                real_path="/test.js",
                extension=".js",
                size=100,
                mtime=1.0,
                ctime=1.0,
                atime=1.0,
                mode=stat.S_IFREG | 0o644,
            ),
        ]
        layer.build_index(files)

        result = layer.list_directory("")

        assert result == ["js", "py"]  # Sorted

    def test_list_directory_category(self):
        """Test listing files in a category."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

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

        result = layer.list_directory("cat1")

        assert result == ["file1.txt", "file2.txt"]  # Sorted

    def test_list_directory_nonexistent_category(self):
        """Test listing a category that doesn't exist."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

        files = []
        layer.build_index(files)

        result = layer.list_directory("nonexistent")

        assert result == []

    def test_list_directory_empty_index(self):
        """Test listing with empty index."""

        def classifier(f):
            return "cat1"

        layer = ClassifierLayer("test", classifier)

        layer.build_index([])

        result = layer.list_directory("")

        assert result == []


class TestBuiltinClassifierExtension:
    """Test extension classifier."""

    def test_extension_classifier_python(self):
        """Test classifying Python file."""
        file_info = FileInfo(
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

        result = BuiltinClassifiers.extension(file_info)

        assert result == "py"

    def test_extension_classifier_javascript(self):
        """Test classifying JavaScript file."""
        file_info = FileInfo(
            name="app.js",
            path="app.js",
            real_path="/app.js",
            extension=".js",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.extension(file_info)

        assert result == "js"

    def test_extension_classifier_no_extension(self):
        """Test classifying file with no extension."""
        file_info = FileInfo(
            name="README",
            path="README",
            real_path="/README",
            extension="",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.extension(file_info)

        assert result == "no-extension"

    def test_extension_classifier_multiple_dots(self):
        """Test classifying file with multiple dots."""
        file_info = FileInfo(
            name="archive.tar.gz",
            path="archive.tar.gz",
            real_path="/archive.tar.gz",
            extension=".gz",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.extension(file_info)

        assert result == "gz"

    def test_extension_classifier_hidden_file(self):
        """Test classifying hidden file."""
        file_info = FileInfo(
            name=".gitignore",
            path=".gitignore",
            real_path="/.gitignore",
            extension="",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.extension(file_info)

        assert result == "no-extension"


class TestBuiltinClassifierSize:
    """Test size classifier."""

    def test_size_classifier_empty(self):
        """Test classifying empty file."""
        file_info = FileInfo(
            name="empty.txt",
            path="empty.txt",
            real_path="/empty.txt",
            extension=".txt",
            size=0,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "empty"

    def test_size_classifier_tiny(self):
        """Test classifying tiny file (<1KB)."""
        file_info = FileInfo(
            name="tiny.txt",
            path="tiny.txt",
            real_path="/tiny.txt",
            extension=".txt",
            size=512,  # 512 bytes
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "tiny"

    def test_size_classifier_small(self):
        """Test classifying small file (<1MB)."""
        file_info = FileInfo(
            name="small.txt",
            path="small.txt",
            real_path="/small.txt",
            extension=".txt",
            size=500 * 1024,  # 500 KB
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "small"

    def test_size_classifier_medium(self):
        """Test classifying medium file (<100MB)."""
        file_info = FileInfo(
            name="medium.bin",
            path="medium.bin",
            real_path="/medium.bin",
            extension=".bin",
            size=50 * 1024 * 1024,  # 50 MB
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "medium"

    def test_size_classifier_large(self):
        """Test classifying large file (<1GB)."""
        file_info = FileInfo(
            name="large.bin",
            path="large.bin",
            real_path="/large.bin",
            extension=".bin",
            size=500 * 1024 * 1024,  # 500 MB
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "large"

    def test_size_classifier_huge(self):
        """Test classifying huge file (>=1GB)."""
        file_info = FileInfo(
            name="huge.bin",
            path="huge.bin",
            real_path="/huge.bin",
            extension=".bin",
            size=2 * 1024 * 1024 * 1024,  # 2 GB
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.size(file_info)

        assert result == "huge"

    def test_size_classifier_edge_cases(self):
        """Test size classifier at boundary values."""
        # Exactly 1KB (should be small, not tiny)
        file_info = FileInfo(
            name="1kb.txt",
            path="1kb.txt",
            real_path="/1kb.txt",
            extension=".txt",
            size=1024,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )
        assert BuiltinClassifiers.size(file_info) == "small"

        # Exactly 1MB (should be medium, not small)
        file_info = FileInfo(
            name="1mb.txt",
            path="1mb.txt",
            real_path="/1mb.txt",
            extension=".txt",
            size=1024 * 1024,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )
        assert BuiltinClassifiers.size(file_info) == "medium"


class TestBuiltinClassifierMimeType:
    """Test MIME type classifier."""

    def test_mimetype_classifier_text(self):
        """Test classifying text file."""
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

        result = BuiltinClassifiers.mimetype(file_info)

        assert result == "text"

    def test_mimetype_classifier_image(self):
        """Test classifying image file."""
        file_info = FileInfo(
            name="photo.jpg",
            path="photo.jpg",
            real_path="/photo.jpg",
            extension=".jpg",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.mimetype(file_info)

        assert result == "image"

    def test_mimetype_classifier_application(self):
        """Test classifying application file."""
        file_info = FileInfo(
            name="app.pdf",
            path="app.pdf",
            real_path="/app.pdf",
            extension=".pdf",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.mimetype(file_info)

        assert result == "application"

    def test_mimetype_classifier_unknown(self):
        """Test classifying unknown file type."""
        file_info = FileInfo(
            name="unknown.unknownext123",
            path="unknown.unknownext123",
            real_path="/unknown.unknownext123",
            extension=".unknownext123",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.mimetype(file_info)

        assert result == "unknown"


class TestBuiltinClassifierGitStatus:
    """Test Git status classifier."""

    def test_git_status_unknown_when_not_in_repo(self, temp_dir):
        """Test Git status returns unknown when not in a repository."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        file_info = FileInfo.from_path(str(test_file))

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "unknown"

    @patch("subprocess.run")
    def test_git_status_ignored(self, mock_run):
        """Test Git status for ignored file."""
        # Mock check-ignore (returns 0 for ignored files)
        mock_run.return_value = MagicMock(returncode=0)

        file_info = FileInfo(
            name="ignored.txt",
            path="ignored.txt",
            real_path="/repo/ignored.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "ignored"

    @patch("subprocess.run")
    def test_git_status_untracked(self, mock_run):
        """Test Git status for untracked file."""

        # Mock check-ignore (returns 1 for not ignored)
        # Then mock git status (returns "?? file")
        def run_side_effect(*args, **kwargs):
            if "check-ignore" in args[0]:
                raise subprocess.CalledProcessError(1, "check-ignore")
            else:
                return MagicMock(returncode=0, stdout="?? ignored.txt\n")

        mock_run.side_effect = run_side_effect

        file_info = FileInfo(
            name="new.txt",
            path="new.txt",
            real_path="/repo/new.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "untracked"

    @patch("subprocess.run")
    def test_git_status_modified(self, mock_run):
        """Test Git status for modified file."""

        def run_side_effect(*args, **kwargs):
            if "check-ignore" in args[0]:
                raise subprocess.CalledProcessError(1, "check-ignore")
            else:
                return MagicMock(returncode=0, stdout=" M modified.txt\n")

        mock_run.side_effect = run_side_effect

        file_info = FileInfo(
            name="modified.txt",
            path="modified.txt",
            real_path="/repo/modified.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "modified"

    @patch("subprocess.run")
    def test_git_status_staged(self, mock_run):
        """Test Git status for staged file."""

        def run_side_effect(*args, **kwargs):
            if "check-ignore" in args[0]:
                raise subprocess.CalledProcessError(1, "check-ignore")
            else:
                return MagicMock(returncode=0, stdout="A  staged.txt\n")

        mock_run.side_effect = run_side_effect

        file_info = FileInfo(
            name="staged.txt",
            path="staged.txt",
            real_path="/repo/staged.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "staged"

    @patch("subprocess.run")
    def test_git_status_committed(self, mock_run):
        """Test Git status for committed file with no changes."""

        def run_side_effect(*args, **kwargs):
            if "check-ignore" in args[0]:
                raise subprocess.CalledProcessError(1, "check-ignore")
            else:
                return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = run_side_effect

        file_info = FileInfo(
            name="committed.txt",
            path="committed.txt",
            real_path="/repo/committed.txt",
            extension=".txt",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "committed"

    @patch("subprocess.run")
    def test_git_status_timeout(self, mock_run):
        """Test Git status when subprocess times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 1)

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

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "unknown"

    @patch("subprocess.run")
    def test_git_status_unknown_status_code(self, mock_run):
        """Test Git status with unrecognized status code."""

        def run_side_effect(*args, **kwargs):
            if "check-ignore" in args[0]:
                raise subprocess.CalledProcessError(1, "check-ignore")
            else:
                # Return unrecognized status code
                return MagicMock(returncode=0, stdout="XY test.txt\n")

        mock_run.side_effect = run_side_effect

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

        result = BuiltinClassifiers.git_status(file_info)

        assert result == "unknown"


class TestBuiltinClassifierPattern:
    """Test pattern classifier."""

    def test_pattern_classifier_single_rule(self):
        """Test pattern classifier with single rule."""
        rules = [{"pattern": "*.py", "category": "python"}]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
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

        result = classifier(file_info)

        assert result == "python"

    def test_pattern_classifier_multiple_rules_first_match(self):
        """Test pattern classifier with multiple rules (first match wins)."""
        rules = [
            {"pattern": "test_*.py", "category": "tests"},
            {"pattern": "*.py", "category": "src"},
        ]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
            name="test_main.py",
            path="test_main.py",
            real_path="/test_main.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "tests"  # First rule matches

    def test_pattern_classifier_multiple_rules_second_match(self):
        """Test pattern classifier where second rule matches."""
        rules = [
            {"pattern": "test_*.py", "category": "tests"},
            {"pattern": "*.py", "category": "src"},
        ]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
            name="main.py",
            path="main.py",
            real_path="/main.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "src"  # Second rule matches

    def test_pattern_classifier_no_match(self):
        """Test pattern classifier when no rule matches."""
        rules = [{"pattern": "*.py", "category": "python"}]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
            name="test.js",
            path="test.js",
            real_path="/test.js",
            extension=".js",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "other"  # Default category

    def test_pattern_classifier_with_subdirectories(self):
        """Test pattern classifier with path containing subdirectories."""
        rules = [
            {"pattern": "src/**/*.py", "category": "source"},
            {"pattern": "tests/**/*.py", "category": "tests"},
        ]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
            name="main.py",
            path="src/app/main.py",
            real_path="/project/src/app/main.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )

        result = classifier(file_info)

        assert result == "source"

    def test_pattern_classifier_complex_patterns(self):
        """Test pattern classifier with complex glob patterns."""
        rules = [
            {"pattern": "**/__pycache__/**", "category": "cache"},
            {"pattern": "**/test_*.py", "category": "tests"},
            {"pattern": "*.py", "category": "src"},
        ]
        classifier = BuiltinClassifiers.pattern(rules)

        # Test cache pattern
        file_info = FileInfo(
            name="module.pyc",
            path="src/__pycache__/module.pyc",
            real_path="/src/__pycache__/module.pyc",
            extension=".pyc",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )
        assert classifier(file_info) == "cache"

        # Test test pattern
        file_info = FileInfo(
            name="test_app.py",
            path="tests/test_app.py",
            real_path="/tests/test_app.py",
            extension=".py",
            size=100,
            mtime=1.0,
            ctime=1.0,
            atime=1.0,
            mode=stat.S_IFREG | 0o644,
        )
        assert classifier(file_info) == "tests"

    def test_pattern_classifier_empty_rules(self):
        """Test pattern classifier with empty rules list."""
        rules = []
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
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

        result = classifier(file_info)

        assert result == "other"

    def test_pattern_classifier_missing_keys(self):
        """Test pattern classifier with rules missing keys."""
        rules = [
            {},  # No pattern or category
            {"pattern": "*.py"},  # No category
        ]
        classifier = BuiltinClassifiers.pattern(rules)

        file_info = FileInfo(
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

        result = classifier(file_info)

        assert result == "other"  # Default category when pattern/category missing


# Fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
