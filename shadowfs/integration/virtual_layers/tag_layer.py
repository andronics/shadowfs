"""
ShadowFS Virtual Layers: Tag Layer.

This module provides tag-based virtual layers that organize files
by tags extracted from various sources (xattr, sidecar files, custom extractors).

Example structure:
    by-tag/
        work/
            document.pdf
            report.txt
        personal/
            photo.jpg
            letter.txt
        important/
            document.pdf  # Same file can appear in multiple tags
            contract.pdf
"""

import json
import os
from typing import Callable, Dict, List, Optional, Set

from shadowfs.integration.virtual_layers.base import FileInfo, VirtualLayer

# Type alias for tag extractor functions
TagExtractor = Callable[[FileInfo], List[str]]


class TagLayer(VirtualLayer):
    """
    Virtual layer that organizes files by tags.

    Files are organized by tags extracted from various sources. A single file
    can appear in multiple tag directories if it has multiple tags.

    Attributes:
        name: Layer name (used as root directory)
        extractors: List of tag extractor functions
        index: Dictionary mapping tag → list of files
    """

    def __init__(self, name: str, extractors: Optional[List[TagExtractor]] = None):
        """
        Initialize the tag layer.

        Args:
            name: Layer name (e.g., "by-tag", "by-label")
            extractors: List of tag extractor functions. Each extractor takes
                       a FileInfo and returns a list of tags (strings).
                       If None, uses default extractors (xattr).
        """
        super().__init__(name)
        self.extractors = extractors if extractors is not None else [BuiltinExtractors.xattr()]
        # Index: tag → [files that have this tag]
        self.index: Dict[str, List[FileInfo]] = {}

    def build_index(self, files: List[FileInfo]) -> None:
        """
        Build the tag index from a list of files.

        Each file is processed through all extractors to get its tags.
        Files with multiple tags appear in multiple tag directories.

        Args:
            files: List of files to index
        """
        # Clear existing index
        self.index = {}

        # Extract tags for each file
        for file_info in files:
            # Skip directories (only index regular files)
            if not file_info.is_file:
                continue

            # Collect tags from all extractors
            tags: Set[str] = set()
            for extractor in self.extractors:
                try:
                    file_tags = extractor(file_info)
                    # Add valid tags (non-empty strings after stripping whitespace)
                    tags.update(
                        tag.strip() for tag in file_tags if isinstance(tag, str) and tag.strip()
                    )
                except Exception:
                    # Skip files that cause extractor errors
                    continue

            # Add file to each tag's index
            for tag in tags:
                if tag not in self.index:
                    self.index[tag] = []
                self.index[tag].append(file_info)

    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Virtual path format: "tag/filename"

        Args:
            virtual_path: Path relative to this layer (e.g., "work/document.pdf")

        Returns:
            Absolute path to the real file, or None if not found
        """
        # Split path into tag and filename
        parts = virtual_path.split(os.sep, 1)

        if len(parts) != 2:
            # Invalid path (should be tag/filename)
            return None

        tag, filename = parts

        # Check if tag exists
        if tag not in self.index:
            return None

        # Find file in tag
        for file_info in self.index[tag]:
            if file_info.name == filename:
                return file_info.real_path

        return None

    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            subpath: Path relative to this layer
                    "" lists tags (root)
                    "tag" lists files with that tag

        Returns:
            List of names (directories or files)
        """
        if not subpath:
            # Root: list all tags
            return sorted(self.index.keys())

        # List files in a tag
        if subpath in self.index:
            return sorted([f.name for f in self.index[subpath]])

        # Tag doesn't exist
        return []


class BuiltinExtractors:
    """Built-in tag extractor functions."""

    @staticmethod
    def xattr(attr_name: str = "user.tags") -> TagExtractor:
        """
        Create an extractor that reads tags from extended attributes.

        Extended attributes (xattr) are filesystem metadata attached to files.
        Tags are stored as comma-separated values.

        Args:
            attr_name: Name of the xattr attribute (default: "user.tags")

        Returns:
            Tag extractor function

        Example:
            # Set tags on a file (Linux):
            # setfattr -n user.tags -v "work,important" document.pdf

            # Use in TagLayer:
            >>> extractor = BuiltinExtractors.xattr("user.tags")
            >>> layer = TagLayer("by-tag", [extractor])
        """

        def xattr_extractor(file_info: FileInfo) -> List[str]:
            """Extract tags from xattr."""
            try:
                import xattr as xattr_module

                # Read xattr value
                tags_bytes = xattr_module.getxattr(file_info.real_path, attr_name)
                tags_str = tags_bytes.decode("utf-8")

                # Split comma-separated tags and strip whitespace
                tags = [tag.strip() for tag in tags_str.split(",")]
                return [tag for tag in tags if tag]  # Filter empty strings

            except (ImportError, OSError, KeyError):
                # xattr module not available, file doesn't have attr, or permission denied
                return []

        return xattr_extractor

    @staticmethod
    def sidecar(suffix: str = ".tags") -> TagExtractor:
        """
        Create an extractor that reads tags from sidecar files.

        Sidecar files are companion files with the same name plus a suffix.
        Tags are stored as JSON array or comma-separated text.

        Args:
            suffix: Suffix for sidecar files (default: ".tags")

        Returns:
            Tag extractor function

        Example:
            # Create sidecar file:
            # document.pdf.tags contains: ["work", "important"]
            # or: work, important

            # Use in TagLayer:
            >>> extractor = BuiltinExtractors.sidecar(".tags")
            >>> layer = TagLayer("by-tag", [extractor])
        """

        def sidecar_extractor(file_info: FileInfo) -> List[str]:
            """Extract tags from sidecar file."""
            sidecar_path = file_info.real_path + suffix

            try:
                with open(sidecar_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                # Try JSON format first
                if content.startswith("["):
                    try:
                        tags = json.loads(content)
                        if isinstance(tags, list):
                            return [str(tag) for tag in tags if tag]
                    except json.JSONDecodeError:
                        pass

                # Fall back to comma-separated format
                tags = [tag.strip() for tag in content.split(",")]
                return [tag for tag in tags if tag]

            except (OSError, UnicodeDecodeError):
                # Sidecar file doesn't exist or can't be read
                return []

        return sidecar_extractor

    @staticmethod
    def filename_pattern(patterns: Dict[str, str]) -> TagExtractor:
        """
        Create an extractor that assigns tags based on filename patterns.

        Tags are assigned by matching the filename against glob patterns.

        Args:
            patterns: Dict mapping glob pattern → tag
                     Example: {"test_*.py": "tests", "*.md": "docs"}

        Returns:
            Tag extractor function

        Example:
            >>> patterns = {
            ...     "test_*.py": "tests",
            ...     "*.md": "docs",
            ...     "*-draft*": "drafts"
            ... }
            >>> extractor = BuiltinExtractors.filename_pattern(patterns)
            >>> layer = TagLayer("by-tag", [extractor])
        """
        import fnmatch

        def pattern_extractor(file_info: FileInfo) -> List[str]:
            """Extract tags based on filename patterns."""
            tags = []
            for pattern, tag in patterns.items():
                if fnmatch.fnmatch(file_info.name, pattern):
                    tags.append(tag)
            return tags

        return pattern_extractor

    @staticmethod
    def path_pattern(patterns: Dict[str, str]) -> TagExtractor:
        """
        Create an extractor that assigns tags based on path patterns.

        Tags are assigned by matching the full relative path against glob patterns.

        Args:
            patterns: Dict mapping glob pattern → tag
                     Example: {"src/**/*.py": "source", "tests/**": "tests"}

        Returns:
            Tag extractor function

        Example:
            >>> patterns = {
            ...     "src/**/*.py": "source",
            ...     "tests/**": "tests",
            ...     "docs/**": "documentation"
            ... }
            >>> extractor = BuiltinExtractors.path_pattern(patterns)
            >>> layer = TagLayer("by-tag", [extractor])
        """
        import fnmatch

        def path_extractor(file_info: FileInfo) -> List[str]:
            """Extract tags based on path patterns."""
            tags = []
            for pattern, tag in patterns.items():
                if fnmatch.fnmatch(file_info.path, pattern):
                    tags.append(tag)
            return tags

        return path_extractor

    @staticmethod
    def extension_map(extension_tags: Dict[str, List[str]]) -> TagExtractor:
        """
        Create an extractor that assigns tags based on file extension.

        Args:
            extension_tags: Dict mapping extension → list of tags
                           Example: {".py": ["code", "python"], ".md": ["docs"]}

        Returns:
            Tag extractor function

        Example:
            >>> ext_tags = {
            ...     ".py": ["code", "python"],
            ...     ".js": ["code", "javascript"],
            ...     ".md": ["docs", "markdown"]
            ... }
            >>> extractor = BuiltinExtractors.extension_map(ext_tags)
            >>> layer = TagLayer("by-tag", [extractor])
        """

        def extension_extractor(file_info: FileInfo) -> List[str]:
            """Extract tags based on file extension."""
            ext = file_info.extension.lower()
            return extension_tags.get(ext, [])

        return extension_extractor
