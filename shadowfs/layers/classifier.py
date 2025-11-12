"""
ShadowFS Virtual Layers: Classifier Layer.

This module provides classification-based virtual layers that organize files
by a single property (extension, size, pattern, MIME type, etc.).

Example structure:
    by-type/
        python/
            project1.py
            project2.py
        javascript/
            app.js
        docs/
            README.md
"""

import mimetypes
import os
import subprocess
from typing import Callable, Dict, List, Optional

from shadowfs.layers.base import FileInfo, Layer


class ClassifierLayer(Layer):
    """
    Virtual layer that classifies files by a single property.

    Files are organized into categories based on a classifier function.
    The classifier function takes a FileInfo and returns a category name (string).

    Attributes:
        name: Layer name (used as root directory)
        classifier: Function that maps FileInfo → category name
        index: Dictionary mapping category → list of files
    """

    def __init__(self, name: str, classifier: Callable[[FileInfo], str]):
        """
        Initialize the classifier layer.

        Args:
            name: Layer name (e.g., "by-type", "by-size")
            classifier: Function that takes FileInfo and returns category name
        """
        super().__init__(name)
        self.classifier = classifier
        self.index: Dict[str, List[FileInfo]] = {}

    def build_index(self, files: List[FileInfo]) -> None:
        """
        Build the category index from a list of files.

        Each file is classified into a category using the classifier function.
        Files are grouped by category in the index.

        Args:
            files: List of files to index
        """
        # Clear existing index
        self.index = {}

        # Classify each file
        for file_info in files:
            # Skip directories (only index regular files)
            if not file_info.is_file:
                continue

            try:
                category = self.classifier(file_info)

                # Skip files that don't get a category (empty string)
                if not category:
                    continue

                # Add to category
                if category not in self.index:
                    self.index[category] = []
                self.index[category].append(file_info)

            except Exception:
                # Skip files that cause classifier errors
                continue

    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Virtual path format: "category/filename"

        Args:
            virtual_path: Path relative to this layer (e.g., "python/project.py")

        Returns:
            Absolute path to the real file, or None if not found
        """
        # Split path into category and filename
        parts = virtual_path.split(os.sep, 1)

        if len(parts) != 2:
            # Invalid path (should be category/filename)
            return None

        category, filename = parts

        # Check if category exists
        if category not in self.index:
            return None

        # Find file in category
        for file_info in self.index[category]:
            if file_info.name == filename:
                return file_info.real_path

        return None

    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            subpath: Path relative to this layer
                    "" lists categories (root)
                    "category" lists files in that category

        Returns:
            List of names (directories or files)
        """
        if not subpath:
            # Root: list all categories
            return sorted(self.index.keys())

        # List files in a category
        if subpath in self.index:
            return sorted([f.name for f in self.index[subpath]])

        # Category doesn't exist
        return []


class BuiltinClassifiers:
    """Built-in classifier functions for common use cases."""

    @staticmethod
    def extension(file_info: FileInfo) -> str:
        """
        Classify by file extension.

        Maps extension to language/type name:
        - .py → python
        - .js → javascript
        - .md → markdown
        - etc.

        Args:
            file_info: File to classify

        Returns:
            Category name based on extension (without dot)
        """
        ext = file_info.extension.lstrip(".")
        if not ext:
            return "no-extension"
        return ext

    @staticmethod
    def size(file_info: FileInfo) -> str:
        """
        Classify by file size.

        Size ranges:
        - 0 bytes: empty
        - < 1KB: tiny
        - < 1MB: small
        - < 100MB: medium
        - < 1GB: large
        - >= 1GB: huge

        Args:
            file_info: File to classify

        Returns:
            Size category name
        """
        size = file_info.size

        if size == 0:
            return "empty"
        elif size < 1024:  # < 1KB
            return "tiny"
        elif size < 1024 * 1024:  # < 1MB
            return "small"
        elif size < 100 * 1024 * 1024:  # < 100MB
            return "medium"
        elif size < 1024 * 1024 * 1024:  # < 1GB
            return "large"
        else:
            return "huge"

    @staticmethod
    def mimetype(file_info: FileInfo) -> str:
        """
        Classify by MIME type.

        Uses Python's mimetypes module for detection.

        Args:
            file_info: File to classify

        Returns:
            MIME type category (e.g., "text", "image", "application")
        """
        mime_type, _ = mimetypes.guess_type(file_info.name)

        if not mime_type:
            return "unknown"

        # Extract main type (before '/')
        main_type = mime_type.split("/")[0]
        return main_type

    @staticmethod
    def git_status(file_info: FileInfo) -> str:
        """
        Classify by Git status.

        Categories:
        - untracked: File not in Git
        - modified: File has uncommitted changes
        - staged: File is staged for commit
        - committed: File is committed with no changes
        - ignored: File is in .gitignore

        Args:
            file_info: File to classify

        Returns:
            Git status category

        Note:
            Requires Git to be installed and file to be in a Git repository.
            Falls back to "unknown" if Git is not available.
        """
        try:
            # Get the directory containing the file
            file_dir = os.path.dirname(file_info.real_path)

            # Check if file is ignored
            try:
                subprocess.run(
                    ["git", "check-ignore", "-q", file_info.real_path],
                    cwd=file_dir,
                    check=True,
                    capture_output=True,
                    timeout=1,
                )
                return "ignored"
            except subprocess.CalledProcessError:
                # Not ignored, continue checking status
                pass

            # Get git status for the file
            result = subprocess.run(
                ["git", "status", "--porcelain", file_info.real_path],
                cwd=file_dir,
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode != 0:
                return "unknown"

            status = result.stdout.strip()

            if not status:
                # File is tracked and has no changes
                return "committed"
            elif status.startswith("??"):
                return "untracked"
            elif status.startswith("M ") or status.startswith(" M"):
                return "modified"
            elif status.startswith("A ") or status.startswith("AM"):
                return "staged"
            else:
                return "unknown"

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # Git not available or timeout
            return "unknown"

    @staticmethod
    def pattern(rules: List[Dict[str, str]]) -> Callable[[FileInfo], str]:
        """
        Create a pattern-based classifier.

        Rules are evaluated in order. First matching pattern determines category.

        Args:
            rules: List of dicts with 'pattern' and 'category' keys
                  Example: [
                      {'pattern': 'test_*.py', 'category': 'tests'},
                      {'pattern': '*.py', 'category': 'src'},
                  ]

        Returns:
            Classifier function that uses pattern matching

        Example:
            >>> rules = [
            ...     {'pattern': 'test_*.py', 'category': 'tests'},
            ...     {'pattern': '*.py', 'category': 'src'},
            ... ]
            >>> classifier = BuiltinClassifiers.pattern(rules)
            >>> layer = ClassifierLayer('by-pattern', classifier)
        """
        import fnmatch

        def pattern_classifier(file_info: FileInfo) -> str:
            """Classify file based on pattern rules."""
            for rule in rules:
                pattern = rule.get("pattern", "")
                category = rule.get("category", "other")

                if fnmatch.fnmatch(file_info.path, pattern):
                    return category

            # No pattern matched
            return "other"

        return pattern_classifier
