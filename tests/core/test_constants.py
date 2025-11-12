"""Tests for constants and type definitions."""
import stat
from typing import get_args

import pytest

from shadowfs.core.constants import (
    DEFAULT_CONFIG,
    SHADOWFS_API_VERSION,
    SHADOWFS_VERSION,
    ConfigKey,
    ErrorCode,
    FileAttributes,
    FileType,
    LayerType,
    Limits,
    RuleType,
    TransformType,
)


class TestErrorCodes:
    """Test error code definitions."""

    def test_error_codes_unique(self):
        """All error codes must have unique values."""
        codes = [e.value for e in ErrorCode]
        assert len(codes) == len(set(codes))

    def test_success_is_zero(self):
        """SUCCESS code must be 0 for system compatibility."""
        assert ErrorCode.SUCCESS == 0

    def test_error_codes_in_range(self):
        """All error codes must be in 0-9 range (Meta-Architecture)."""
        for code in ErrorCode:
            assert 0 <= code.value <= 9

    def test_all_required_codes_present(self):
        """All required error codes must be defined."""
        required = [
            "SUCCESS",
            "INVALID_INPUT",
            "NOT_FOUND",
            "PERMISSION_DENIED",
            "CONFLICT",
            "DEPENDENCY_ERROR",
            "INTERNAL_ERROR",
            "TIMEOUT",
            "RATE_LIMITED",
            "DEGRADED",
        ]
        actual = [e.name for e in ErrorCode]
        assert set(required) == set(actual)

    def test_error_code_values(self):
        """Test specific error code values."""
        assert ErrorCode.SUCCESS == 0
        assert ErrorCode.INVALID_INPUT == 1
        assert ErrorCode.NOT_FOUND == 2
        assert ErrorCode.PERMISSION_DENIED == 3
        assert ErrorCode.CONFLICT == 4
        assert ErrorCode.DEPENDENCY_ERROR == 5
        assert ErrorCode.INTERNAL_ERROR == 6
        assert ErrorCode.TIMEOUT == 7
        assert ErrorCode.RATE_LIMITED == 8
        assert ErrorCode.DEGRADED == 9


class TestFileAttributes:
    """Test file attributes structure."""

    def test_create_file_attributes(self):
        """Can create FileAttributes with all fields."""
        attrs = FileAttributes(
            st_mode=stat.S_IFREG | 0o644,
            st_ino=12345,
            st_dev=8080,
            st_nlink=1,
            st_uid=1000,
            st_gid=1000,
            st_size=1024,
            st_atime=1000000.0,
            st_mtime=2000000.0,
            st_ctime=3000000.0,
        )

        assert attrs.st_size == 1024
        assert attrs.st_uid == 1000
        assert attrs.st_atime == 1000000.0
        assert attrs.st_mtime == 2000000.0
        assert attrs.st_ctime == 3000000.0
        assert attrs.is_file
        assert not attrs.is_dir
        assert not attrs.is_symlink

    def test_file_attributes_immutable(self):
        """FileAttributes should be immutable."""
        attrs = FileAttributes(
            st_mode=stat.S_IFREG | 0o644,
            st_ino=1,
            st_dev=1,
            st_nlink=1,
            st_uid=1000,
            st_gid=1000,
            st_size=100,
            st_atime=1.0,
            st_mtime=1.0,
            st_ctime=1.0,
        )

        with pytest.raises(AttributeError):
            attrs.st_size = 200

    def test_directory_detection(self):
        """Test directory type detection."""
        attrs = FileAttributes(
            st_mode=stat.S_IFDIR | 0o755,
            st_ino=1,
            st_dev=1,
            st_nlink=2,
            st_uid=0,
            st_gid=0,
            st_size=4096,
            st_atime=1.0,
            st_mtime=1.0,
            st_ctime=1.0,
        )

        assert attrs.is_dir
        assert not attrs.is_file
        assert not attrs.is_symlink

    def test_symlink_detection(self):
        """Test symlink type detection."""
        attrs = FileAttributes(
            st_mode=stat.S_IFLNK | 0o777,
            st_ino=1,
            st_dev=1,
            st_nlink=1,
            st_uid=1000,
            st_gid=1000,
            st_size=100,
            st_atime=1.0,
            st_mtime=1.0,
            st_ctime=1.0,
        )

        assert attrs.is_symlink
        assert not attrs.is_file
        assert not attrs.is_dir


class TestLimits:
    """Test system limits."""

    def test_file_size_limits_positive(self):
        """All size limits must be positive."""
        assert Limits.MAX_FILE_SIZE > 0
        assert Limits.MAX_TRANSFORM_OUTPUT > 0
        assert Limits.MAX_MEMORY_PER_TRANSFORM > 0

    def test_time_limits_reasonable(self):
        """Time limits must be reasonable."""
        assert 1 <= Limits.MAX_TRANSFORM_TIME <= 300
        assert 1 <= Limits.DEFAULT_OPERATION_TIMEOUT <= 60

    def test_path_limits_standard(self):
        """Path limits should match system standards."""
        assert Limits.MAX_PATH_LENGTH == 4096
        assert Limits.MAX_FILENAME_LENGTH == 255
        assert Limits.MAX_SYMLINK_DEPTH >= 5

    def test_cache_configuration_valid(self):
        """Cache configuration must be valid."""
        assert Limits.DEFAULT_CACHE_SIZE_MB >= 64
        assert Limits.DEFAULT_CACHE_TTL_SECONDS >= 60
        assert Limits.ATTR_CACHE_ENTRIES >= 1000
        assert Limits.CONTENT_CACHE_SIZE_MB >= 64
        assert Limits.TRANSFORM_CACHE_SIZE_MB >= 128

    def test_virtual_layer_limits(self):
        """Virtual layer limits must be reasonable."""
        assert Limits.MAX_VIRTUAL_LAYERS > 0
        assert Limits.MAX_INDEX_BUILD_TIME > 0

    def test_rate_limits(self):
        """Rate limits must be positive."""
        assert Limits.MAX_OPERATIONS_PER_SECOND > 0
        assert Limits.MAX_TRANSFORMS_PER_SECOND > 0

    def test_specific_limit_values(self):
        """Test specific limit values."""
        assert Limits.MAX_FILE_SIZE == 2 * 1024 * 1024 * 1024
        assert Limits.MAX_TRANSFORM_OUTPUT == 100 * 1024 * 1024
        assert Limits.MAX_PATH_LENGTH == 4096
        assert Limits.MAX_FILENAME_LENGTH == 255
        assert Limits.MAX_SYMLINK_DEPTH == 10
        assert Limits.MAX_VIRTUAL_LAYERS == 50


class TestFileType:
    """Test file type enumeration."""

    def test_all_types_defined(self):
        """All standard file types must be defined."""
        expected_types = [
            "REGULAR",
            "DIRECTORY",
            "SYMLINK",
            "BLOCK_DEVICE",
            "CHARACTER_DEVICE",
            "FIFO",
            "SOCKET",
            "UNKNOWN",
        ]
        actual_types = [t.name for t in FileType]
        assert set(expected_types) == set(actual_types)

    def test_from_mode_regular_file(self):
        """Test file type detection for regular files."""
        mode = stat.S_IFREG | 0o644
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.REGULAR

    def test_from_mode_directory(self):
        """Test file type detection for directories."""
        mode = stat.S_IFDIR | 0o755
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.DIRECTORY

    def test_from_mode_symlink(self):
        """Test file type detection for symlinks."""
        mode = stat.S_IFLNK | 0o777
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.SYMLINK

    def test_from_mode_block_device(self):
        """Test file type detection for block devices."""
        mode = stat.S_IFBLK | 0o660
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.BLOCK_DEVICE

    def test_from_mode_character_device(self):
        """Test file type detection for character devices."""
        mode = stat.S_IFCHR | 0o660
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.CHARACTER_DEVICE

    def test_from_mode_fifo(self):
        """Test file type detection for FIFOs."""
        mode = stat.S_IFIFO | 0o644
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.FIFO

    def test_from_mode_socket(self):
        """Test file type detection for sockets."""
        mode = stat.S_IFSOCK | 0o755
        file_type = FileType.from_mode(mode)
        assert file_type == FileType.SOCKET

    def test_from_mode_unknown(self):
        """Test file type detection for unknown types."""
        file_type = FileType.from_mode(0)
        assert file_type == FileType.UNKNOWN

    def test_file_type_values(self):
        """Test file type enum values."""
        assert FileType.REGULAR.value == "regular"
        assert FileType.DIRECTORY.value == "directory"
        assert FileType.SYMLINK.value == "symlink"
        assert FileType.BLOCK_DEVICE.value == "block"
        assert FileType.CHARACTER_DEVICE.value == "char"
        assert FileType.FIFO.value == "fifo"
        assert FileType.SOCKET.value == "socket"
        assert FileType.UNKNOWN.value == "unknown"


class TestEnumerations:
    """Test other enumerations."""

    def test_rule_types(self):
        """Test rule type enumeration."""
        assert RuleType.INCLUDE.value == "include"
        assert RuleType.EXCLUDE.value == "exclude"
        assert RuleType.TRANSFORM.value == "transform"

    def test_rule_types_complete(self):
        """All rule types defined."""
        expected = ["INCLUDE", "EXCLUDE", "TRANSFORM"]
        actual = [t.name for t in RuleType]
        assert set(expected) == set(actual)

    def test_transform_types(self):
        """Test transform type enumeration."""
        expected = ["TEMPLATE", "COMPRESS", "DECOMPRESS", "ENCRYPT", "DECRYPT", "CONVERT"]
        actual = [t.name for t in TransformType]
        assert set(expected) == set(actual)

    def test_transform_type_values(self):
        """Test transform type values."""
        assert TransformType.TEMPLATE.value == "template"
        assert TransformType.COMPRESS.value == "compress"
        assert TransformType.DECOMPRESS.value == "decompress"
        assert TransformType.ENCRYPT.value == "encrypt"
        assert TransformType.DECRYPT.value == "decrypt"
        assert TransformType.CONVERT.value == "convert"

    def test_virtual_layer_types(self):
        """Test virtual layer type enumeration."""
        expected = ["CLASSIFIER", "TAG", "DATE", "HIERARCHICAL", "PATTERN", "COMPUTED"]
        actual = [t.name for t in LayerType]
        assert set(expected) == set(actual)

    def test_virtual_layer_type_values(self):
        """Test virtual layer type values."""
        assert LayerType.CLASSIFIER.value == "classifier"
        assert LayerType.TAG.value == "tag"
        assert LayerType.DATE.value == "date"
        assert LayerType.HIERARCHICAL.value == "hierarchical"
        assert LayerType.PATTERN.value == "pattern"
        assert LayerType.COMPUTED.value == "computed"


class TestConfigKeys:
    """Test configuration key constants."""

    def test_top_level_keys(self):
        """Test top-level configuration keys."""
        assert ConfigKey.VERSION == "version"
        assert ConfigKey.SOURCES == "sources"
        assert ConfigKey.RULES == "rules"
        assert ConfigKey.TRANSFORMS == "transforms"
        assert ConfigKey.VIRTUAL_LAYERS == "virtual_layers"
        assert ConfigKey.CACHE == "cache"
        assert ConfigKey.LOGGING == "logging"
        assert ConfigKey.METRICS == "metrics"

    def test_source_config_keys(self):
        """Test source configuration keys."""
        assert ConfigKey.SOURCE_PATH == "path"
        assert ConfigKey.SOURCE_PRIORITY == "priority"
        assert ConfigKey.SOURCE_READONLY == "readonly"

    def test_rule_config_keys(self):
        """Test rule configuration keys."""
        assert ConfigKey.RULE_NAME == "name"
        assert ConfigKey.RULE_TYPE == "type"
        assert ConfigKey.RULE_PATTERN == "pattern"
        assert ConfigKey.RULE_PATTERNS == "patterns"

    def test_transform_config_keys(self):
        """Test transform configuration keys."""
        assert ConfigKey.TRANSFORM_NAME == "name"
        assert ConfigKey.TRANSFORM_TYPE == "type"
        assert ConfigKey.TRANSFORM_PATTERN == "pattern"

    def test_cache_config_keys(self):
        """Test cache configuration keys."""
        assert ConfigKey.CACHE_ENABLED == "enabled"
        assert ConfigKey.CACHE_SIZE_MB == "max_size_mb"
        assert ConfigKey.CACHE_TTL == "ttl_seconds"

    def test_default_config_structure(self):
        """Test default configuration structure."""
        assert ConfigKey.VERSION in DEFAULT_CONFIG
        assert ConfigKey.SOURCES in DEFAULT_CONFIG
        assert ConfigKey.CACHE in DEFAULT_CONFIG

        cache_config = DEFAULT_CONFIG[ConfigKey.CACHE]
        assert ConfigKey.CACHE_ENABLED in cache_config
        assert ConfigKey.CACHE_SIZE_MB in cache_config
        assert cache_config[ConfigKey.CACHE_SIZE_MB] == Limits.DEFAULT_CACHE_SIZE_MB
        assert cache_config[ConfigKey.CACHE_TTL] == Limits.DEFAULT_CACHE_TTL_SECONDS

    def test_default_config_values(self):
        """Test default configuration values."""
        assert DEFAULT_CONFIG[ConfigKey.VERSION] == "1.0"
        assert DEFAULT_CONFIG[ConfigKey.SOURCES] == []
        assert DEFAULT_CONFIG[ConfigKey.RULES] == []
        assert DEFAULT_CONFIG[ConfigKey.TRANSFORMS] == []
        assert DEFAULT_CONFIG[ConfigKey.VIRTUAL_LAYERS] == []

        # Check cache defaults
        cache = DEFAULT_CONFIG[ConfigKey.CACHE]
        assert cache[ConfigKey.CACHE_ENABLED] is True
        assert cache[ConfigKey.CACHE_SIZE_MB] == 512
        assert cache[ConfigKey.CACHE_TTL] == 300

        # Check logging defaults
        logging = DEFAULT_CONFIG[ConfigKey.LOGGING]
        assert logging["level"] == "INFO"
        assert logging["file"] is None

        # Check metrics defaults
        metrics = DEFAULT_CONFIG[ConfigKey.METRICS]
        assert metrics["enabled"] is False
        assert metrics["port"] == 9090


class TestVersion:
    """Test version information."""

    def test_version_format(self):
        """Version must follow semantic versioning."""
        parts = SHADOWFS_VERSION.split(".")
        assert len(parts) == 3

        for part in parts:
            assert part.isdigit()
            assert int(part) >= 0

    def test_version_value(self):
        """Test specific version value."""
        assert SHADOWFS_VERSION == "1.0.0"

    def test_api_version(self):
        """Test API version."""
        assert isinstance(SHADOWFS_API_VERSION, int)
        assert SHADOWFS_API_VERSION == 1
