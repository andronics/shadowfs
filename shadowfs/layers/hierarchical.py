"""
ShadowFS Virtual Layers: Hierarchical Layer.

This module provides hierarchical virtual layers that organize files
using multiple levels of classification in sequence.

Example structure:
    by-project/
        projectA/
            src/
                main.py
                utils.py
            tests/
                test_main.py
        projectB/
            src/
                app.py
            docs/
                README.md

Each level is determined by a classifier function applied in sequence.
"""

from typing import Any, Callable, Dict, List, Optional, Union

from shadowfs.layers.base import FileInfo, Layer

# Type alias for classifier functions
Classifier = Callable[[FileInfo], str]

# Type alias for the nested index structure
# Can be either a dict (interior node) or list of files (leaf node)
IndexNode = Union[Dict[str, "IndexNode"], List[FileInfo]]


class HierarchicalLayer(Layer):
    """
    Virtual layer that organizes files using multiple levels of classification.

    Files are organized into a hierarchical structure where each level
    is determined by a classifier function. This creates a tree-like
    directory structure with arbitrary depth.

    Attributes:
        name: Layer name (used as root directory)
        classifiers: List of classifier functions, one per level
        index: Nested dictionary structure storing the hierarchy
    """

    def __init__(self, name: str, classifiers: List[Classifier]):
        """
        Initialize the hierarchical layer.

        Args:
            name: Layer name (e.g., "by-project", "by-category")
            classifiers: List of classifier functions. Each classifier takes
                        a FileInfo and returns a category string.
                        The classifiers are applied in sequence to create
                        the hierarchy levels.

        Raises:
            ValueError: If classifiers list is empty

        Example:
            >>> def project_classifier(f):
            ...     # Extract project from path
            ...     return f.path.split('/')[0]
            >>>
            >>> def type_classifier(f):
            ...     # Classify by file type
            ...     if f.path.endswith('.py'):
            ...         return 'src'
            ...     return 'other'
            >>>
            >>> layer = HierarchicalLayer("by-project", [project_classifier, type_classifier])
            >>> # Creates: by-project/projectA/src/file.py
        """
        super().__init__(name)

        if not classifiers:
            raise ValueError("Classifiers list cannot be empty")

        self.classifiers = classifiers
        self.index: IndexNode = {}

    def build_index(self, files: List[FileInfo]) -> None:
        """
        Build the hierarchical index from a list of files.

        Each file is classified at each level using the classifier chain.
        Files are organized into a tree structure based on the classifications.

        Args:
            files: List of files to index
        """
        # Clear existing index
        self.index = {}

        # Index each file
        for file_info in files:
            # Skip directories (only index regular files)
            if not file_info.is_file:
                continue

            try:
                # Classify file at each level
                categories = []
                for classifier in self.classifiers:
                    category = classifier(file_info)
                    # Skip files that return empty/None categories
                    if not category or not isinstance(category, str):
                        break
                    categories.append(category)
                else:
                    # All classifiers succeeded - add file to index
                    if categories:
                        self._add_to_index(categories, file_info)

            except Exception:
                # Skip files that cause classifier errors
                continue

    def _add_to_index(self, categories: List[str], file_info: FileInfo) -> None:
        """
        Add a file to the nested index structure.

        Navigates through the index creating intermediate dictionaries
        as needed, then adds the file to the leaf list.

        Args:
            categories: List of category strings, one per level
            file_info: File to add
        """
        # Navigate to the correct position in the nested structure
        current: Any = self.index

        # Create intermediate levels as needed
        for category in categories:
            if category not in current:
                current[category] = {}
            current = current[category]

        # At the leaf level, current should be a dict that will hold files
        # We need to add a special marker for the files list
        if "__files__" not in current:
            current["__files__"] = []

        current["__files__"].append(file_info)

    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Virtual path format: "level1/level2/.../levelN/filename"

        Args:
            virtual_path: Path relative to this layer

        Returns:
            Absolute path to the real file, or None if not found
        """
        # Split path into components
        parts = virtual_path.split("/")

        if len(parts) < len(self.classifiers) + 1:
            # Path doesn't have enough levels (categories + filename)
            return None

        # Extract categories and filename
        categories = parts[: len(self.classifiers)]
        filename = parts[len(self.classifiers)]

        # Navigate to the file list
        files = self._get_files_at_path(categories)
        if files is None:
            return None

        # Find file by name
        for file_info in files:
            if file_info.name == filename:
                return file_info.real_path

        return None

    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            subpath: Path relative to this layer
                    "" lists level 1 categories
                    "cat1" lists level 2 categories
                    "cat1/cat2" lists level 3 categories
                    "cat1/cat2/.../catN" lists files at leaf level

        Returns:
            List of names (directories or files)
        """
        if not subpath:
            # Root: list all level 1 categories
            return sorted([k for k in self.index.keys() if k != "__files__"])

        # Split path into categories
        categories = subpath.split("/")

        # Navigate to the appropriate level
        current: Any = self.index
        for category in categories:
            if not isinstance(current, dict) or category not in current:
                return []
            current = current[category]

        if not isinstance(current, dict):
            return []

        # Check if we're at the leaf level (all classifiers applied)
        if len(categories) == len(self.classifiers):
            # List files
            files = current.get("__files__", [])
            return sorted([f.name for f in files])
        else:
            # List subcategories (filter out __files__ marker)
            return sorted([k for k in current.keys() if k != "__files__"])

    def _get_files_at_path(self, categories: List[str]) -> Optional[List[FileInfo]]:
        """
        Get the list of files at a specific path in the hierarchy.

        Args:
            categories: List of category strings defining the path

        Returns:
            List of FileInfo objects at that path, or None if path doesn't exist
        """
        # Navigate to the target location
        current: Any = self.index

        for category in categories:
            if not isinstance(current, dict) or category not in current:
                return None
            current = current[category]

        if not isinstance(current, dict):
            return None

        # Return the files list (empty list if no files)
        return current.get("__files__", [])


# Built-in classifier factory functions
class BuiltinClassifiers:
    """Factory functions for creating common classifiers."""

    @staticmethod
    def by_path_component(index: int) -> Classifier:
        """
        Create a classifier that extracts a path component by index.

        Args:
            index: Index of path component (0-based)
                  Example: For "src/utils/file.py":
                  - index 0 → "src"
                  - index 1 → "utils"

        Returns:
            Classifier function

        Example:
            >>> # Extract project name (first directory)
            >>> project = BuiltinClassifiers.by_path_component(0)
            >>> # Extract subdirectory (second directory)
            >>> subdir = BuiltinClassifiers.by_path_component(1)
            >>> layer = HierarchicalLayer("by-project", [project, subdir])
        """

        def path_component_classifier(file_info: FileInfo) -> str:
            """Extract path component by index."""
            parts = file_info.path.split("/")
            if index < len(parts) - 1:  # -1 to exclude filename
                return parts[index]
            return ""

        return path_component_classifier

    @staticmethod
    def by_extension_group(groups: Dict[str, List[str]]) -> Classifier:
        """
        Create a classifier that groups files by extension.

        Args:
            groups: Dict mapping group name → list of extensions
                   Example: {"code": [".py", ".js"], "docs": [".md", ".txt"]}

        Returns:
            Classifier function

        Example:
            >>> groups = {
            ...     "code": [".py", ".js", ".ts"],
            ...     "docs": [".md", ".rst", ".txt"],
            ...     "config": [".yaml", ".json", ".toml"]
            ... }
            >>> ext_classifier = BuiltinClassifiers.by_extension_group(groups)
        """

        def extension_group_classifier(file_info: FileInfo) -> str:
            """Classify by extension group."""
            ext = file_info.extension.lower()
            for group, extensions in groups.items():
                if ext in extensions:
                    return group
            return "other"

        return extension_group_classifier

    @staticmethod
    def by_size_range(ranges: Dict[str, tuple[int, int]]) -> Classifier:
        """
        Create a classifier that categorizes files by size range.

        Args:
            ranges: Dict mapping category → (min_bytes, max_bytes)
                   Use float('inf') for unbounded maximum

        Returns:
            Classifier function

        Example:
            >>> ranges = {
            ...     "small": (0, 1024),           # 0-1KB
            ...     "medium": (1024, 1048576),    # 1KB-1MB
            ...     "large": (1048576, float('inf'))  # 1MB+
            ... }
            >>> size_classifier = BuiltinClassifiers.by_size_range(ranges)
        """

        def size_range_classifier(file_info: FileInfo) -> str:
            """Classify by file size."""
            for category, (min_size, max_size) in ranges.items():
                if min_size <= file_info.size < max_size:
                    return category
            return "unknown"

        return size_range_classifier
