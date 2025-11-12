"""
FUSE filesystem operations for ShadowFS.

This module implements the FUSE (Filesystem in Userspace) interface,
providing the core operations needed for a working filesystem:
- Metadata operations (getattr, readlink, statfs)
- Directory operations (readdir, mkdir, rmdir)
- File operations (open, read, write, release, create, unlink)
- Permission operations (chmod, chown)

The operations integrate with:
- LayerManager for path resolution
- RuleEngine for file visibility filtering
- TransformPipeline for content transformation
- CacheManager for performance optimization
"""

import errno
import logging
import os
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fuse import FUSE, FuseOSError, Operations

from shadowfs.core.cache import CacheConfig, CacheLevel, CacheManager
from shadowfs.core.config import ConfigManager
from shadowfs.core.logging import Logger
from shadowfs.layers.manager import LayerManager
from shadowfs.rules.engine import RuleEngine
from shadowfs.transforms.pipeline import TransformPipeline


@dataclass
class FileHandle:
    """Represents an open file handle."""

    fd: int  # OS file descriptor
    real_path: str  # Resolved real path
    flags: int  # Open flags (O_RDONLY, O_WRONLY, etc.)
    virtual_path: str  # Virtual path used to open file


class ShadowFSOperations(Operations):
    """
    FUSE filesystem operations implementation for ShadowFS.

    This class implements the FUSE Operations interface, providing a complete
    filesystem that integrates virtual layers, transforms, and filtering rules.

    Integration Points:
    - LayerManager: Resolves virtual paths to real paths
    - RuleEngine: Filters file visibility based on rules
    - TransformPipeline: Applies transformations to file content
    - CacheManager: Caches paths, attributes, and content

    Thread Safety:
    - File handle tracking uses locks
    - Cache operations are thread-safe
    - Multiple concurrent FUSE operations supported
    """

    def __init__(
        self,
        config: ConfigManager,
        virtual_layer_manager: Optional[LayerManager] = None,
        rule_engine: Optional[RuleEngine] = None,
        transform_pipeline: Optional[TransformPipeline] = None,
        cache: Optional[CacheManager] = None,
    ):
        """
        Initialize FUSE operations.

        Args:
            config: Configuration manager
            virtual_layer_manager: Virtual layer manager (created if None)
            rule_engine: Rule engine for filtering (created if None)
            transform_pipeline: Transform pipeline (created if None)
            cache: Cache manager (created if None)
        """
        self.config = config
        self.logger = Logger("shadowfs.fuse")

        # Initialize managers with defaults
        # (Detailed configuration loading delegated to caller)
        # Note: Use explicit None checks because some objects have __len__ that can return 0
        self.virtual_layer_manager = (
            virtual_layer_manager if virtual_layer_manager is not None else LayerManager()
        )
        self.rule_engine = rule_engine if rule_engine is not None else RuleEngine()
        self.transform_pipeline = (
            transform_pipeline if transform_pipeline is not None else TransformPipeline()
        )
        self.cache = cache if cache is not None else CacheManager()

        # File handle tracking
        self.fds: Dict[int, FileHandle] = {}
        self.fd_counter = 0
        self.fd_lock = threading.Lock()

        # Configuration flags (use getattr to safely access config dict)
        self.readonly = getattr(config, "_config", {}).get("readonly", True)
        self.allow_other = getattr(config, "_config", {}).get("allow_other", False)

        self.logger.info("FUSE operations initialized")

    # =========================================================================
    # Path Resolution
    # =========================================================================

    def _resolve_path(self, virtual_path: str) -> Optional[str]:
        """
        Resolve virtual path to real filesystem path.

        This method:
        1. Checks cache for previously resolved paths
        2. Uses LayerManager to resolve virtual paths
        3. Applies RuleEngine filtering
        4. Caches successful resolutions

        Args:
            virtual_path: Virtual path (e.g., "/by-type/py/file.py")

        Returns:
            Real filesystem path if found and allowed, None otherwise
        """
        # Normalize path
        virtual_path = os.path.normpath(virtual_path)

        # Check cache first
        cached = self.cache.get("path", virtual_path)
        if cached:
            self.logger.debug(f"Path cache hit: {virtual_path} -> {cached}")
            return cached

        # Try virtual layer manager
        try:
            real_path = self.virtual_layer_manager.resolve_path(virtual_path)
        except Exception as e:
            self.logger.warning(f"Path resolution failed for {virtual_path}: {e}")
            real_path = None

        # If not found in virtual layers, check if it's a direct source path
        if not real_path:
            # Try each source directory
            sources = getattr(self.config, "_config", {}).get("sources", [])
            for source in sources:
                source_path = source.get("path", "")
                potential_path = os.path.join(source_path, virtual_path.lstrip("/"))
                if os.path.exists(potential_path):
                    real_path = potential_path
                    break

        # Apply rule engine filtering
        if real_path:
            if self.rule_engine.should_show(real_path):
                # Cache successful resolution
                self.cache.set("path", virtual_path, real_path)
                self.logger.debug(f"Path resolved: {virtual_path} -> {real_path}")
                return real_path
            else:
                self.logger.debug(f"Path filtered by rules: {real_path}")
                return None

        self.logger.debug(f"Path not found: {virtual_path}")
        return None

    def _get_file_stat(self, path: str) -> os.stat_result:
        """
        Get file statistics for a path.

        Args:
            path: Real filesystem path

        Returns:
            os.stat_result object

        Raises:
            FuseOSError: If stat fails
        """
        try:
            return os.lstat(path)
        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # FUSE Metadata Operations
    # =========================================================================

    def getattr(self, path: str, fh: Optional[int] = None) -> Dict[str, Any]:
        """
        Get file attributes (equivalent to stat()).

        Args:
            path: Virtual path
            fh: Optional file handle (if file is open)

        Returns:
            Dictionary with stat attributes

        Raises:
            FuseOSError: ENOENT if path doesn't exist
        """
        # Check cache for attributes
        cached = self.cache.get("attr", path, level=CacheLevel.L1)
        if cached:
            return cached

        # Resolve path
        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        # Get file stat
        st = self._get_file_stat(real_path)

        # Convert to dictionary
        attrs = {
            "st_mode": st.st_mode,
            "st_nlink": st.st_nlink,
            "st_size": st.st_size,
            "st_ctime": st.st_ctime,
            "st_mtime": st.st_mtime,
            "st_atime": st.st_atime,
            "st_uid": st.st_uid,
            "st_gid": st.st_gid,
        }

        # Cache attributes (use L1 for frequently accessed metadata)
        self.cache.set("attr", path, attrs, level=CacheLevel.L1)

        return attrs

    def readlink(self, path: str) -> str:
        """
        Read symlink target.

        Args:
            path: Virtual path to symlink

        Returns:
            Target path

        Raises:
            FuseOSError: If not a symlink or doesn't exist
        """
        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            target = os.readlink(real_path)
            return target
        except OSError as e:
            raise FuseOSError(e.errno)

    def statfs(self, path: str) -> Dict[str, Any]:
        """
        Get filesystem statistics.

        Args:
            path: Virtual path (typically "/")

        Returns:
            Dictionary with filesystem stats

        Raises:
            FuseOSError: On error
        """
        # Use first source directory for statfs
        sources = getattr(self.config, "_config", {}).get("sources", [])
        if not sources:
            raise FuseOSError(errno.ENOENT)

        source_path = sources[0].get("path", "/")

        try:
            stv = os.statvfs(source_path)
            return {
                "f_bsize": stv.f_bsize,
                "f_frsize": stv.f_frsize,
                "f_blocks": stv.f_blocks,
                "f_bfree": stv.f_bfree,
                "f_bavail": stv.f_bavail,
                "f_files": stv.f_files,
                "f_ffree": stv.f_ffree,
                "f_favail": stv.f_favail,
            }
        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # FUSE Directory Operations
    # =========================================================================

    def readdir(self, path: str, fh: int) -> List[str]:
        """
        List directory contents.

        This method:
        1. Checks if path is a virtual layer directory
        2. Applies rule engine filtering
        3. Returns merged results from sources or virtual layer

        Args:
            path: Virtual directory path
            fh: File handle (unused)

        Returns:
            List of directory entries (including "." and "..")

        Raises:
            FuseOSError: ENOENT if directory doesn't exist
        """
        entries = [".", ".."]

        # Check cache
        cached = self.cache.get("readdir", path, level=CacheLevel.L1)
        if cached:
            return cached

        # Check if this is a virtual layer directory
        try:
            virtual_entries = self.virtual_layer_manager.list_directory(path)
            if virtual_entries:
                # Filter entries through rule engine
                filtered = []
                for entry in virtual_entries:
                    entry_path = os.path.join(path, entry)
                    real_path = self._resolve_path(entry_path)
                    if real_path and self.rule_engine.should_show(real_path):
                        filtered.append(entry)

                result = entries + filtered
                self.cache.set("readdir", path, result, level=CacheLevel.L1)
                return result
        except Exception as e:
            self.logger.debug(f"Virtual layer listing failed for {path}: {e}")

        # Not a virtual layer, try real directory
        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        if not os.path.isdir(real_path):
            raise FuseOSError(errno.ENOTDIR)

        try:
            # List directory
            dir_entries = os.listdir(real_path)

            # Filter through rule engine
            filtered = []
            for entry in dir_entries:
                entry_real_path = os.path.join(real_path, entry)
                if self.rule_engine.should_show(entry_real_path):
                    filtered.append(entry)

            result = entries + filtered
            self.cache.set("readdir", path, result, level=CacheLevel.L1)
            return result

        except OSError as e:
            raise FuseOSError(e.errno)

    def mkdir(self, path: str, mode: int) -> None:
        """
        Create directory.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path for new directory
            mode: Directory permissions

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if parent doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        # Resolve parent directory
        parent_path = os.path.dirname(path)
        real_parent = self._resolve_path(parent_path)
        if not real_parent:
            raise FuseOSError(errno.ENOENT)

        # Create directory in real filesystem
        dir_name = os.path.basename(path)
        real_path = os.path.join(real_parent, dir_name)

        try:
            os.mkdir(real_path, mode)
            # Invalidate directory listing cache
            self.cache.invalidate("readdir", parent_path)
        except OSError as e:
            raise FuseOSError(e.errno)

    def rmdir(self, path: str) -> None:
        """
        Remove directory.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to directory

        Raises:
            FuseOSError: EROFS if readonly, ENOTEMPTY if not empty
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            os.rmdir(real_path)
            # Invalidate caches
            parent_path = os.path.dirname(path)
            self.cache.invalidate("readdir", parent_path)
            self.cache.invalidate("attr", path)
            self.cache.invalidate("path", path)
        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # FUSE File Operations
    # =========================================================================

    def open(self, path: str, flags: int) -> int:
        """
        Open file and return file handle.

        This method:
        1. Resolves virtual path to real path
        2. Opens the underlying file
        3. Allocates a file handle for tracking
        4. Returns file handle ID

        Args:
            path: Virtual path to file
            flags: Open flags (O_RDONLY, O_WRONLY, O_RDWR, etc.)

        Returns:
            File handle ID

        Raises:
            FuseOSError: ENOENT if file doesn't exist, EROFS if write on readonly
        """
        # Check if write operation on readonly filesystem
        if self.readonly and (flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT)):
            raise FuseOSError(errno.EROFS)

        # Resolve path
        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            # Open file in underlying filesystem
            fd = os.open(real_path, flags)

            # Allocate file handle
            fh = self._allocate_file_handle(fd, real_path, path, flags)

            self.logger.debug(f"Opened file: {path} -> {real_path} (fh={fh})")
            return fh

        except OSError as e:
            raise FuseOSError(e.errno)

    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        """
        Read file content with optional transformation.

        This method:
        1. Reads content from underlying file
        2. Applies transform pipeline if configured
        3. Returns transformed content
        4. Caches transformed results

        Args:
            path: Virtual path to file
            size: Number of bytes to read
            offset: Byte offset to start reading from
            fh: File handle from open()

        Returns:
            File content (possibly transformed)

        Raises:
            FuseOSError: EBADF if invalid handle
        """
        # Get file handle
        handle = self._get_file_handle(fh)

        try:
            # Check cache for transformed content
            cache_key = f"{path}:transformed"
            cached_content = self.cache.get("content", cache_key, level=CacheLevel.L2)

            if cached_content is not None:
                # Return slice from cached content
                return cached_content[offset : offset + size]

            # Read entire file for transformation
            with os.fdopen(os.dup(handle.fd), "rb") as f:
                f.seek(0)
                content = f.read()

            # Apply transform pipeline
            try:
                result = self.transform_pipeline.apply(content, path)

                # Extract transformed content from result
                if result.success:
                    transformed = result.content
                else:
                    # Transform failed, use original content
                    self.logger.warning(f"Transform failed for {path}: {result.error}")
                    transformed = content

                # Cache transformed content
                self.cache.set("content", cache_key, transformed, level=CacheLevel.L2)

                # Return requested slice
                return transformed[offset : offset + size]

            except Exception as e:
                # If transform raises exception, return original content
                self.logger.warning(f"Transform failed for {path}: {e}")
                return content[offset : offset + size]

        except OSError as e:
            raise FuseOSError(e.errno)

    def write(self, path: str, data: bytes, offset: int, fh: int) -> int:
        """
        Write data to file.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to file
            data: Data to write
            offset: Byte offset to start writing at
            fh: File handle from open()

        Returns:
            Number of bytes written

        Raises:
            FuseOSError: EROFS if readonly, EBADF if invalid handle
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        # Get file handle
        handle = self._get_file_handle(fh)

        try:
            # Write to underlying file
            os.lseek(handle.fd, offset, os.SEEK_SET)
            bytes_written = os.write(handle.fd, data)

            # Invalidate caches
            self.cache.invalidate("content", f"{path}:transformed")
            self.cache.invalidate("attr", path)

            self.logger.debug(f"Wrote {bytes_written} bytes to {path}")
            return bytes_written

        except OSError as e:
            raise FuseOSError(e.errno)

    def release(self, path: str, fh: int) -> None:
        """
        Release (close) file handle.

        Args:
            path: Virtual path to file
            fh: File handle from open()
        """
        try:
            # Get file handle
            handle = self._get_file_handle(fh)

            # Close underlying file descriptor
            os.close(handle.fd)

            # Release our file handle
            self._release_file_handle(fh)

            self.logger.debug(f"Closed file: {path} (fh={fh})")

        except OSError:
            # Ignore errors on close
            pass

    def create(self, path: str, mode: int, fi=None) -> int:
        """
        Create and open new file.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path for new file
            mode: File permissions
            fi: File info (unused)

        Returns:
            File handle ID

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if parent doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        # Resolve parent directory
        parent_path = os.path.dirname(path)
        real_parent = self._resolve_path(parent_path)
        if not real_parent:
            raise FuseOSError(errno.ENOENT)

        # Create file in real filesystem
        file_name = os.path.basename(path)
        real_path = os.path.join(real_parent, file_name)

        try:
            # Create file with proper permissions
            fd = os.open(real_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)

            # Allocate file handle
            fh = self._allocate_file_handle(fd, real_path, path, os.O_WRONLY)

            # Invalidate directory listing cache
            self.cache.invalidate("readdir", parent_path)

            self.logger.debug(f"Created file: {path} -> {real_path}")
            return fh

        except OSError as e:
            raise FuseOSError(e.errno)

    def unlink(self, path: str) -> None:
        """
        Delete file.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to file

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            os.unlink(real_path)

            # Invalidate caches
            parent_path = os.path.dirname(path)
            self.cache.invalidate("readdir", parent_path)
            self.cache.invalidate("attr", path)
            self.cache.invalidate("path", path)
            self.cache.invalidate("content", f"{path}:transformed")

            self.logger.debug(f"Deleted file: {path}")

        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # FUSE Permission Operations
    # =========================================================================

    def chmod(self, path: str, mode: int) -> None:
        """
        Change file permissions.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to file
            mode: New permission mode

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            os.chmod(real_path, mode)

            # Invalidate attribute cache
            self.cache.invalidate("attr", path)

            self.logger.debug(f"Changed permissions: {path} -> {oct(mode)}")

        except OSError as e:
            raise FuseOSError(e.errno)

    def chown(self, path: str, uid: int, gid: int) -> None:
        """
        Change file ownership.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to file
            uid: New user ID (-1 to leave unchanged)
            gid: New group ID (-1 to leave unchanged)

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            os.chown(real_path, uid, gid)

            # Invalidate attribute cache
            self.cache.invalidate("attr", path)

            self.logger.debug(f"Changed ownership: {path} -> uid={uid}, gid={gid}")

        except OSError as e:
            raise FuseOSError(e.errno)

    def utimens(self, path: str, times=None) -> None:
        """
        Update file access and modification times.

        Only allowed if filesystem is not readonly.

        Args:
            path: Virtual path to file
            times: (atime, mtime) tuple or None for current time

        Raises:
            FuseOSError: EROFS if readonly, ENOENT if doesn't exist
        """
        if self.readonly:
            raise FuseOSError(errno.EROFS)

        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            if times is None:
                # Use current time
                os.utime(real_path, None)
            else:
                # Extract times from tuple
                # times can be (atime_sec, mtime_sec) or ((atime_sec, atime_nsec), (mtime_sec, mtime_nsec))
                if isinstance(times[0], tuple):
                    atime = times[0][0] + times[0][1] / 1e9
                    mtime = times[1][0] + times[1][1] / 1e9
                else:
                    atime, mtime = times

                os.utime(real_path, (atime, mtime))

            # Invalidate attribute cache
            self.cache.invalidate("attr", path)

            self.logger.debug(f"Updated times: {path}")

        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # FUSE Additional Operations
    # =========================================================================

    def access(self, path: str, mode: int) -> None:
        """
        Check file access permissions.

        Args:
            path: Virtual path to file
            mode: Access mode to check (R_OK, W_OK, X_OK, F_OK)

        Raises:
            FuseOSError: ENOENT if doesn't exist, EACCES if permission denied
        """
        real_path = self._resolve_path(path)
        if not real_path:
            raise FuseOSError(errno.ENOENT)

        try:
            # Check if write access requested on readonly filesystem
            if self.readonly and (mode & os.W_OK):
                raise FuseOSError(errno.EROFS)

            # Check access on real file
            if not os.access(real_path, mode):
                raise FuseOSError(errno.EACCES)

        except OSError as e:
            raise FuseOSError(e.errno)

    def fsync(self, path: str, datasync: bool, fh: int) -> None:
        """
        Flush file buffers to disk.

        Args:
            path: Virtual path to file
            datasync: If True, only flush data (not metadata)
            fh: File handle from open()

        Raises:
            FuseOSError: EBADF if invalid handle
        """
        # Get file handle
        handle = self._get_file_handle(fh)

        try:
            if datasync:
                # Flush data only
                os.fdatasync(handle.fd)
            else:
                # Flush data and metadata
                os.fsync(handle.fd)

            self.logger.debug(f"Synced file: {path} (datasync={datasync})")

        except OSError as e:
            raise FuseOSError(e.errno)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _allocate_file_handle(self, fd: int, real_path: str, virtual_path: str, flags: int) -> int:
        """
        Allocate a new file handle.

        Thread-safe allocation of file handle IDs.

        Args:
            fd: OS file descriptor
            real_path: Real filesystem path
            virtual_path: Virtual path
            flags: Open flags

        Returns:
            File handle ID
        """
        with self.fd_lock:
            fh_id = self.fd_counter
            self.fds[fh_id] = FileHandle(
                fd=fd, real_path=real_path, virtual_path=virtual_path, flags=flags
            )
            self.fd_counter += 1
            return fh_id

    def _get_file_handle(self, fh: int) -> FileHandle:
        """
        Get file handle by ID.

        Args:
            fh: File handle ID

        Returns:
            FileHandle object

        Raises:
            FuseOSError: EBADF if handle doesn't exist
        """
        if fh not in self.fds:
            raise FuseOSError(errno.EBADF)
        return self.fds[fh]

    def _release_file_handle(self, fh: int) -> None:
        """
        Release file handle.

        Thread-safe release of file handle.

        Args:
            fh: File handle ID
        """
        with self.fd_lock:
            if fh in self.fds:
                del self.fds[fh]

    def invalidate_cache(self, path: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            path: Specific path to invalidate, or None for all
        """
        if path:
            self.cache.invalidate("path", path)
            self.cache.invalidate("attr", path)
            self.cache.invalidate("readdir", path)
            self.logger.debug(f"Cache invalidated for: {path}")
        else:
            self.cache.clear()
            self.logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get filesystem statistics.

        Returns:
            Dictionary with statistics
        """
        sources = getattr(self.config, "_config", {}).get("sources", [])
        return {
            "open_files": len(self.fds),
            "cache_size": len(self.cache.caches) if hasattr(self.cache, "caches") else 0,
            "sources": len(sources),
            "virtual_layers": len(self.virtual_layer_manager.layers),
            "readonly": self.readonly,
        }
