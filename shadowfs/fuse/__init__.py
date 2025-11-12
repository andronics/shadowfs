"""ShadowFS FUSE Interface.

This module implements the FUSE filesystem interface for ShadowFS:
- ShadowFS: FUSE callback implementations
- ControlServer: Runtime control and management API

Usage:
    from shadowfs.fuse import ShadowFS
    from shadowfs.core.config import ConfigManager

    config = ConfigManager()
    ops = ShadowFS(config)
"""

from shadowfs.fuse.control import ControlServer
from shadowfs.fuse.operations import FileHandle, ShadowFS

__all__ = [
    "ShadowFS",
    "FileHandle",
    "ControlServer",
]
