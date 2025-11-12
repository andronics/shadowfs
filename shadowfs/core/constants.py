"""
ShadowFS Foundation: Constants and Type Definitions

This module provides system-wide constants, error codes, and type definitions
following Meta-Architecture v1.0.0 principles.
"""
from dataclasses import dataclass
from enum import Enum, IntEnum
from pathlib import Path as PathType
from typing import NewType, Optional, TypeAlias

# Version information
SHADOWFS_VERSION = "1.0.0"
SHADOWFS_API_VERSION = 1


# Error codes (Meta-Architecture compliant: 0-9 range)
class ErrorCode(IntEnum):
    """Standardized error codes for ShadowFS operations."""

    SUCCESS = 0  # Operation completed successfully
    INVALID_INPUT = 1  # Bad path, invalid configuration
    NOT_FOUND = 2  # File or resource doesn't exist
    PERMISSION_DENIED = 3  # Insufficient permissions
    CONFLICT = 4  # Resource conflict (locked, exists)
    DEPENDENCY_ERROR = 5  # Missing dependency (transform library)
    INTERNAL_ERROR = 6  # Bug in ShadowFS
    TIMEOUT = 7  # Operation timed out
    RATE_LIMITED = 8  # Too many operations
    DEGRADED = 9  # Running with reduced functionality


# Type aliases for clarity
FilePath: TypeAlias = str
VirtualPath: TypeAlias = str
RealPath: TypeAlias = str
FileContent: TypeAlias = bytes
Pattern: TypeAlias = str

# NewTypes for type safety
SourcePath = NewType("SourcePath", str)
MountPath = NewType("MountPath", str)
LayerName = NewType("LayerName", str)
TransformName = NewType("TransformName", str)


# File attributes matching os.stat_result
@dataclass(frozen=True)
class FileAttributes:
    """File attributes matching os.stat_result structure."""

    st_mode: int  # File mode (type and permissions)
    st_ino: int  # Inode number
    st_dev: int  # Device ID
    st_nlink: int  # Number of hard links
    st_uid: int  # User ID
    st_gid: int  # Group ID
    st_size: int  # File size in bytes
    st_atime: float  # Access time
    st_mtime: float  # Modification time
    st_ctime: float  # Status change time

    @property
    def is_dir(self) -> bool:
        """Check if this is a directory."""
        import stat

        return stat.S_ISDIR(self.st_mode)

    @property
    def is_file(self) -> bool:
        """Check if this is a regular file."""
        import stat

        return stat.S_ISREG(self.st_mode)

    @property
    def is_symlink(self) -> bool:
        """Check if this is a symbolic link."""
        import stat

        return stat.S_ISLNK(self.st_mode)


# Resource limits and defaults
class Limits:
    """System resource limits and default values."""

    # File size limits
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
    MAX_TRANSFORM_OUTPUT = 100 * 1024 * 1024  # 100MB

    # Path limits
    MAX_PATH_LENGTH = 4096
    MAX_FILENAME_LENGTH = 255
    MAX_SYMLINK_DEPTH = 10

    # Time limits
    MAX_TRANSFORM_TIME = 30  # seconds
    DEFAULT_OPERATION_TIMEOUT = 5  # seconds

    # Memory limits
    MAX_MEMORY_PER_TRANSFORM = 100 * 1024 * 1024  # 100MB

    # Cache configuration
    DEFAULT_CACHE_SIZE_MB = 512
    DEFAULT_CACHE_TTL_SECONDS = 300

    # L1: Attribute cache
    ATTR_CACHE_ENTRIES = 10000
    ATTR_CACHE_TTL = 60  # seconds

    # L2: Content cache
    CONTENT_CACHE_SIZE_MB = 512
    CONTENT_CACHE_TTL = 300  # seconds

    # L3: Transform cache
    TRANSFORM_CACHE_SIZE_MB = 1024
    TRANSFORM_CACHE_TTL = 600  # seconds

    # Virtual layer limits
    MAX_VIRTUAL_LAYERS = 50
    MAX_INDEX_BUILD_TIME = 10  # seconds

    # Rate limiting
    MAX_OPERATIONS_PER_SECOND = 1000
    MAX_TRANSFORMS_PER_SECOND = 100


# File type classification
class FileType(Enum):
    """File type classification for virtual layers."""

    REGULAR = "regular"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    BLOCK_DEVICE = "block"
    CHARACTER_DEVICE = "char"
    FIFO = "fifo"
    SOCKET = "socket"
    UNKNOWN = "unknown"

    @classmethod
    def from_mode(cls, mode: int) -> "FileType":
        """Determine file type from mode."""
        import stat

        if stat.S_ISREG(mode):
            return cls.REGULAR
        elif stat.S_ISDIR(mode):
            return cls.DIRECTORY
        elif stat.S_ISLNK(mode):
            return cls.SYMLINK
        elif stat.S_ISBLK(mode):
            return cls.BLOCK_DEVICE
        elif stat.S_ISCHR(mode):
            return cls.CHARACTER_DEVICE
        elif stat.S_ISFIFO(mode):
            return cls.FIFO
        elif stat.S_ISSOCK(mode):
            return cls.SOCKET
        else:
            return cls.UNKNOWN


# Rule types for filtering
class RuleType(Enum):
    """Types of filtering rules."""

    INCLUDE = "include"  # Explicitly include
    EXCLUDE = "exclude"  # Explicitly exclude
    TRANSFORM = "transform"  # Apply transformation


# Transform types
class TransformType(Enum):
    """Types of content transformations."""

    TEMPLATE = "template"  # Template expansion
    COMPRESS = "compress"  # Compression
    DECOMPRESS = "decompress"  # Decompression
    ENCRYPT = "encrypt"  # Encryption
    DECRYPT = "decrypt"  # Decryption
    CONVERT = "convert"  # Format conversion


# Virtual layer types
class LayerType(Enum):
    """Types of virtual organizational layers."""

    CLASSIFIER = "classifier"  # Classify by property
    TAG = "tag"  # Organize by tags
    DATE = "date"  # Time-based hierarchy
    HIERARCHICAL = "hierarchical"  # Multi-level structure
    PATTERN = "pattern"  # Pattern-based organization
    COMPUTED = "computed"  # Dynamically computed


# Configuration keys
class ConfigKey:
    """Configuration key constants."""

    # Top-level keys
    VERSION = "version"
    SOURCES = "sources"
    RULES = "rules"
    TRANSFORMS = "transforms"
    VIRTUAL_LAYERS = "virtual_layers"
    CACHE = "cache"
    LOGGING = "logging"
    METRICS = "metrics"

    # Source configuration
    SOURCE_PATH = "path"
    SOURCE_PRIORITY = "priority"
    SOURCE_READONLY = "readonly"

    # Rule configuration
    RULE_NAME = "name"
    RULE_TYPE = "type"
    RULE_PATTERN = "pattern"
    RULE_PATTERNS = "patterns"

    # Transform configuration
    TRANSFORM_NAME = "name"
    TRANSFORM_TYPE = "type"
    TRANSFORM_PATTERN = "pattern"

    # Cache configuration
    CACHE_ENABLED = "enabled"
    CACHE_SIZE_MB = "max_size_mb"
    CACHE_TTL = "ttl_seconds"


# Default configuration values
DEFAULT_CONFIG = {
    ConfigKey.VERSION: "1.0",
    ConfigKey.SOURCES: [],
    ConfigKey.RULES: [],
    ConfigKey.TRANSFORMS: [],
    ConfigKey.VIRTUAL_LAYERS: [],
    ConfigKey.CACHE: {
        ConfigKey.CACHE_ENABLED: True,
        ConfigKey.CACHE_SIZE_MB: Limits.DEFAULT_CACHE_SIZE_MB,
        ConfigKey.CACHE_TTL: Limits.DEFAULT_CACHE_TTL_SECONDS,
    },
    ConfigKey.LOGGING: {
        "level": "INFO",
        "file": None,
    },
    ConfigKey.METRICS: {
        "enabled": False,
        "port": 9090,
    },
}
