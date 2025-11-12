"""
ShadowFS Virtual Layers: Base Classes and Data Structures.

This module provides the foundation for the virtual layer system:
- FileInfo: Immutable file metadata structure
- VirtualLayer: Abstract base class for all virtual layer implementations

Virtual layers create multiple organizational views over the same files without
duplication, enabling programmable directory structures.
"""

import os
import stat
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class FileInfo:
    """
    Immutable file metadata structure.

    Contains all information needed for classification and organization:
    - Path information (name, relative path, absolute path)
    - File properties (extension, size)
    - Timestamps (mtime, ctime, atime)

    Attributes:
        name: Filename only (e.g., "project.py")
        path: Path relative to source directory (e.g., "src/project.py")
        real_path: Absolute path to actual file (e.g., "/source/src/project.py")
        extension: File extension including dot (e.g., ".py"), empty if none
        size: File size in bytes
        mtime: Modification timestamp (seconds since epoch)
        ctime: Creation/status change timestamp (seconds since epoch)
        atime: Access timestamp (seconds since epoch)
        mode: File mode (permissions and type)
    """

    name: str
    path: str
    real_path: str
    extension: str
    size: int
    mtime: float
    ctime: float
    atime: float
    mode: int

    @classmethod
    def from_path(cls, real_path: str, source_root: Optional[str] = None) -> "FileInfo":
        """
        Create FileInfo from a filesystem path.

        Args:
            real_path: Absolute path to the file
            source_root: Root directory to compute relative path from.
                        If None, uses the file's parent directory.

        Returns:
            FileInfo instance with metadata from the file

        Raises:
            FileNotFoundError: If the path doesn't exist
            OSError: If stat() fails for other reasons
        """
        # Get file stats
        file_stat = os.stat(real_path)

        # Extract filename
        name = os.path.basename(real_path)

        # Compute relative path
        if source_root:
            try:
                path = os.path.relpath(real_path, source_root)
            except ValueError:
                # On Windows, relpath fails if paths are on different drives
                path = real_path
        else:
            # If no source root, just use the filename
            path = name

        # Extract extension (including dot, or empty string)
        _, extension = os.path.splitext(name)

        return cls(
            name=name,
            path=path,
            real_path=os.path.abspath(real_path),
            extension=extension,
            size=file_stat.st_size,
            mtime=file_stat.st_mtime,
            ctime=file_stat.st_ctime,
            atime=file_stat.st_atime,
            mode=file_stat.st_mode,
        )

    @property
    def is_file(self) -> bool:
        """Check if this is a regular file."""
        return stat.S_ISREG(self.mode)

    @property
    def is_dir(self) -> bool:
        """Check if this is a directory."""
        return stat.S_ISDIR(self.mode)

    @property
    def is_symlink(self) -> bool:
        """Check if this is a symbolic link."""
        return stat.S_ISLNK(self.mode)


class VirtualLayer(ABC):
    """
    Abstract base class for all virtual layer implementations.

    A virtual layer creates an organizational view over a set of files,
    providing virtual directory structures without modifying the source files.

    Implementations must provide:
    - build_index(): Build the virtual directory structure from a file list
    - resolve(): Map virtual paths to real filesystem paths
    - list_directory(): List contents of a virtual directory
    - refresh(): Update the index when files change

    The layer can be accessed through a mount point where it appears as a
    regular directory structure, but all paths are dynamically computed.
    """

    def __init__(self, name: str):
        """
        Initialize the virtual layer.

        Args:
            name: Layer name (used as root directory in mount point)
        """
        self.name = name

    @abstractmethod
    def build_index(self, files: List[FileInfo]) -> None:
        """
        Build the virtual layer index from a list of files.

        This method is called when the layer is first created or when a
        full rebuild is needed. Implementations should create their internal
        index structures that map virtual paths to real files.

        Args:
            files: List of files to index
        """
        pass

    @abstractmethod
    def resolve(self, virtual_path: str) -> Optional[str]:
        """
        Resolve a virtual path to a real filesystem path.

        Args:
            virtual_path: Path relative to this layer's root
                         (e.g., "python/project.py" for classifier layer)

        Returns:
            Absolute path to the real file, or None if path doesn't exist
            in this virtual view
        """
        pass

    @abstractmethod
    def list_directory(self, subpath: str = "") -> List[str]:
        """
        List contents of a virtual directory.

        Args:
            subpath: Path relative to this layer's root
                    Empty string lists the layer root
                    (e.g., "" lists categories, "python" lists files in python category)

        Returns:
            List of names (files and/or directories) in the virtual directory
            Empty list if path doesn't exist
        """
        pass

    def refresh(self, files: List[FileInfo]) -> None:
        """
        Refresh the index with an updated file list.

        Default implementation just rebuilds the entire index. Subclasses
        can override for more efficient incremental updates.

        Args:
            files: Updated list of all files
        """
        self.build_index(files)

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"{self.__class__.__name__}(name='{self.name}')"
