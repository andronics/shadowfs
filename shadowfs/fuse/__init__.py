"""ShadowFS FUSE Interface.

This module implements the FUSE filesystem interface for ShadowFS:
- ShadowFSOperations: FUSE callback implementations
- ControlServer: Runtime control and management API

Usage:
    from shadowfs.fuse import ShadowFSOperations
    from shadowfs.core import ConfigManager

    config = ConfigManager()
    ops = ShadowFSOperations(config)
"""

from shadowfs.fuse.control import ControlServer
from shadowfs.fuse.operations import FileHandle, ShadowFSOperations

__all__ = [
    "ShadowFSOperations",
    "FileHandle",
    "ControlServer",
]
