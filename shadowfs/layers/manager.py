"""
ShadowFS Virtual Layers: Manager.

This module provides the LayerManager, the central coordinator
for all virtual layer operations.

The manager:
- Scans source directories to create FileInfo objects
- Registers and manages multiple virtual layers
- Builds indexes for all layers
- Routes path resolution and directory listing to appropriate layers
- Optionally integrates with Phase 2 infrastructure (cache, logging, config)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from shadowfs.layers.base import FileInfo, Layer


class LayerManager:
    """
    Central coordinator for layer operations.

    The manager coordinates all layer functionality:
    - Scans source directories to collect file metadata
    - Registers and manages multiple layers
    - Builds indexes for all registered layers
    - Routes path resolution to the appropriate layer
    - Provides unified directory listing interface

    Attributes:
        sources: List of source directory paths to scan
        layers: Dictionary mapping layer name → Layer instance
        files: List of all FileInfo objects from scanned sources
    """

    def __init__(self, sources: Optional[List[str]] = None):
        """
        Initialize the layer manager.

        Args:
            sources: List of source directory paths to scan.
                    If None, starts with empty source list.

        Example:
            >>> manager = LayerManager(["/data/projects", "/data/docs"])
            >>> manager.add_layer(DateLayer("by-date"))
            >>> manager.scan_sources()
            >>> manager.rebuild_indexes()
        """
        self.sources = sources if sources is not None else []
        self.layers: Dict[str, Layer] = {}
        self.files: List[FileInfo] = []

    def add_source(self, source_path: str) -> None:
        """
        Add a source directory to scan.

        Args:
            source_path: Path to source directory

        Raises:
            ValueError: If path doesn't exist or isn't a directory
        """
        path = Path(source_path)
        if not path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        if not path.is_dir():
            raise ValueError(f"Source path is not a directory: {source_path}")

        if source_path not in self.sources:
            self.sources.append(source_path)

    def add_layer(self, layer: Layer) -> None:
        """
        Register a virtual layer with the manager.

        Args:
            layer: Layer instance to register

        Raises:
            ValueError: If layer name conflicts with existing layer
        """
        if layer.name in self.layers:
            raise ValueError(f"Layer with name '{layer.name}' already registered")

        self.layers[layer.name] = layer

    def remove_layer(self, layer_name: str) -> None:
        """
        Remove a registered virtual layer.

        Args:
            layer_name: Name of layer to remove

        Raises:
            KeyError: If layer doesn't exist
        """
        if layer_name not in self.layers:
            raise KeyError(f"Layer '{layer_name}' not found")

        del self.layers[layer_name]

    def get_layer(self, layer_name: str) -> Optional[Layer]:
        """
        Get a registered layer by name.

        Args:
            layer_name: Name of layer to retrieve

        Returns:
            VirtualLayer instance or None if not found
        """
        return self.layers.get(layer_name)

    def list_layers(self) -> List[str]:
        """
        Get list of all registered layer names.

        Returns:
            List of layer names in sorted order
        """
        return sorted(self.layers.keys())

    def scan_sources(self) -> None:
        """
        Scan all source directories and collect file metadata.

        Walks through all registered source directories recursively,
        creating FileInfo objects for all files found. Results are
        stored in self.files.

        The scan creates FileInfo objects with:
        - Relative paths computed from source root
        - Complete metadata (size, timestamps, permissions)
        - Absolute real_path for file access
        """
        self.files = []

        for source_path in self.sources:
            source_root = Path(source_path).resolve()

            # Walk directory tree
            for dirpath, dirnames, filenames in os.walk(source_root):
                current_dir = Path(dirpath)

                # Add regular files
                for filename in filenames:
                    file_path = current_dir / filename
                    try:
                        file_info = FileInfo.from_path(str(file_path), str(source_root))
                        self.files.append(file_info)
                    except (OSError, PermissionError):
                        # Skip files we can't read
                        continue

    def rebuild_indexes(self) -> None:
        """
        Rebuild indexes for all registered layers.

        Calls build_index() on each layer with the current file list.
        Should be called after:
        - scan_sources() to index newly scanned files
        - Adding new layers
        - Modifying layer configuration
        """
        for layer in self.layers.values():
            layer.build_index(self.files)

    def resolve_path(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Path format: "layer_name/layer_specific_path"

        Args:
            virtual_path: Virtual path (e.g., "by-date/2024/11/12/file.txt")

        Returns:
            Absolute path to real file, or None if not found

        Example:
            >>> manager.resolve_path("by-date/2024/11/12/document.pdf")
            '/source/documents/document.pdf'
        """
        if not virtual_path:
            return None

        # Extract layer name (first component)
        parts = virtual_path.split("/", 1)
        layer_name = parts[0]

        # Check if layer exists
        layer = self.layers.get(layer_name)
        if layer is None:
            return None

        # If path is just the layer name, can't resolve to a file
        if len(parts) == 1:
            return None

        # Delegate to layer
        layer_path = parts[1]
        return layer.resolve(layer_path)

    def list_directory(self, virtual_path: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            virtual_path: Virtual path to list
                         "" (empty) → list all layer names
                         "layer_name" → delegate to layer's list_directory("")
                         "layer_name/subpath" → delegate to layer's list_directory("subpath")

        Returns:
            List of names (directories or files) in sorted order

        Example:
            >>> manager.list_directory("")
            ['by-date', 'by-project', 'by-tag']
            >>> manager.list_directory("by-date")
            ['2023', '2024']
            >>> manager.list_directory("by-date/2024")
            ['01', '02', ..., '11', '12']
        """
        if not virtual_path:
            # Root: list all layer names
            return self.list_layers()

        # Extract layer name
        parts = virtual_path.split("/", 1)
        layer_name = parts[0]

        # Check if layer exists
        layer = self.layers.get(layer_name)
        if layer is None:
            return []

        # Delegate to layer
        if len(parts) == 1:
            # List layer root
            return layer.list_directory("")
        else:
            # List subpath within layer
            layer_path = parts[1]
            return layer.list_directory(layer_path)

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the manager state.

        Returns:
            Dictionary with statistics:
            - source_count: Number of source directories
            - layer_count: Number of registered layers
            - file_count: Total files scanned

        Example:
            >>> stats = manager.get_stats()
            >>> print(f"Indexed {stats['file_count']} files across {stats['layer_count']} layers")
        """
        return {
            "source_count": len(self.sources),
            "layer_count": len(self.layers),
            "file_count": len(self.files),
        }

    def clear_all(self) -> None:
        """
        Clear all state (sources, layers, files).

        Useful for testing or reinitializing the manager.
        """
        self.sources = []
        self.layers = {}
        self.files = []


# Factory functions for creating common layer configurations
class LayerFactory:
    """Factory functions for creating preconfigured virtual layers."""

    @staticmethod
    def create_date_layer(name: str = "by-date", date_field: str = "mtime") -> "Layer":
        """
        Create a date-based layer organized by YYYY/MM/DD.

        Args:
            name: Layer name (default: "by-date")
            date_field: Timestamp field to use ("mtime", "ctime", or "atime")

        Returns:
            Configured DateLayer instance

        Example:
            >>> layer = LayerFactory.create_date_layer("by-modified", "mtime")
            >>> manager.add_layer(layer)
        """
        from shadowfs.layers.date import DateLayer

        return DateLayer(name, date_field)  # type: ignore

    @staticmethod
    def create_extension_layer(name: str = "by-type") -> "Layer":
        """
        Create an extension-based classifier layer.

        Args:
            name: Layer name (default: "by-type")

        Returns:
            Configured ClassifierLayer with extension classifier

        Example:
            >>> layer = LayerFactory.create_extension_layer("by-file-type")
            >>> manager.add_layer(layer)
        """
        from shadowfs.layers.classifier import BuiltinClassifiers, ClassifierLayer

        return ClassifierLayer(name, BuiltinClassifiers.extension)

    @staticmethod
    def create_size_layer(name: str = "by-size") -> "Layer":
        """
        Create a size-based classifier layer.

        Args:
            name: Layer name (default: "by-size")

        Returns:
            Configured ClassifierLayer with size classifier

        Example:
            >>> layer = LayerFactory.create_size_layer("by-file-size")
            >>> manager.add_layer(layer)
        """
        from shadowfs.layers.classifier import BuiltinClassifiers, ClassifierLayer

        return ClassifierLayer(name, BuiltinClassifiers.size)

    @staticmethod
    def create_tag_layer(name: str = "by-tag", extractors: Optional[List] = None) -> "Layer":
        """
        Create a tag-based layer.

        Args:
            name: Layer name (default: "by-tag")
            extractors: List of tag extractors (default: xattr only)

        Returns:
            Configured TagLayer instance

        Example:
            >>> from shadowfs.layers.tag import BuiltinExtractors
            >>> extractors = [BuiltinExtractors.sidecar(".tags")]
            >>> layer = LayerFactory.create_tag_layer("by-label", extractors)
            >>> manager.add_layer(layer)
        """
        from shadowfs.layers.tag import TagLayer

        return TagLayer(name, extractors)
