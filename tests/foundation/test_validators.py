#!/usr/bin/env python3
"""Unit tests for shadowfs.foundation.validators module."""

import re
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.foundation.validators import (
    ValidationError,
    validate_cache_config,
    validate_config,
    validate_file_size,
    validate_glob,
    validate_layer_name,
    validate_path,
    validate_pattern,
    validate_permissions,
    validate_port,
    validate_regex,
    validate_rule_config,
    validate_source_config,
    validate_timeout,
    validate_transform_config,
    validate_version,
    validate_virtual_layer_config,
)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_message(self):
        """Test ValidationError with message."""
        error = ValidationError("Test error")
        assert str(error) == "Test error"

    def test_validation_error_with_error_code(self):
        """Test ValidationError with error code."""
        from shadowfs.foundation.constants import ErrorCode

        error = ValidationError("Invalid value", error_code=ErrorCode.INVALID_INPUT)
        assert error.error_code == ErrorCode.INVALID_INPUT
        assert str(error) == "Invalid value"


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_minimal_config(self):
        """Test minimal valid configuration."""
        config = {"version": "1.0", "sources": [{"path": "/data"}]}
        assert validate_config(config) == True

    def test_valid_full_config(self):
        """Test fully populated valid configuration."""
        config = {
            "version": "1.0",
            "sources": [{"path": "/data", "priority": 1, "readonly": True}],
            "rules": [{"type": "exclude", "pattern": "*.tmp"}],
            "transforms": [{"type": "compress", "pattern": "*.txt", "algorithm": "gzip"}],
            "virtual_layers": [{"name": "by-type", "type": "classifier"}],
            "cache": {"enabled": True, "max_size_mb": 512},
        }
        assert validate_config(config) == True

    def test_invalid_config_missing_version(self):
        """Test config without version."""
        config = {"sources": [{"path": "/data"}]}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "version" in str(exc_info.value).lower()

    def test_config_without_sources(self):
        """Test config without sources is valid (sources are optional)."""
        config = {"version": "1.0"}
        assert validate_config(config) == True

    def test_invalid_config_empty_sources(self):
        """Test config with empty sources list is valid."""
        config = {"version": "1.0", "sources": []}
        assert validate_config(config) == True

    def test_invalid_config_bad_source(self):
        """Test config with invalid source."""
        config = {"version": "1.0", "sources": [{"invalid": "field"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_invalid_config_bad_rule(self):
        """Test config with invalid rule."""
        config = {"version": "1.0", "sources": [{"path": "/data"}], "rules": [{"invalid": "rule"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_invalid_config_bad_transform(self):
        """Test config with invalid transform."""
        config = {
            "version": "1.0",
            "sources": [{"path": "/data"}],
            "transforms": [{"invalid": "transform"}],
        }
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_invalid_config_bad_layer(self):
        """Test config with invalid virtual layer."""
        config = {
            "version": "1.0",
            "sources": [{"path": "/data"}],
            "virtual_layers": [{"invalid": "layer"}],
        }
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_invalid_config_bad_cache(self):
        """Test config with invalid cache settings."""
        config = {"version": "1.0", "sources": [{"path": "/data"}], "cache": {"invalid": "cache"}}
        with pytest.raises(ValidationError):
            validate_config(config)


class TestValidateSourceConfig:
    """Tests for validate_source_config function."""

    def test_valid_minimal_source(self):
        """Test minimal valid source."""
        source = {"path": "/data"}
        assert validate_source_config(source) == True

    def test_valid_full_source(self):
        """Test fully populated source."""
        source = {"path": "/data", "priority": 10, "readonly": False, "name": "main-data"}
        assert validate_source_config(source) == True

    def test_invalid_source_missing_path(self):
        """Test source without path."""
        source = {"priority": 1}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "path" in str(exc_info.value).lower()

    def test_invalid_source_bad_path(self):
        """Test source with invalid path."""
        source = {"path": ""}
        with pytest.raises(ValidationError):
            validate_source_config(source)

    def test_invalid_source_bad_priority(self):
        """Test source with invalid priority."""
        source = {"path": "/data", "priority": -1}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "priority" in str(exc_info.value).lower()

    def test_invalid_source_bad_readonly(self):
        """Test source with non-boolean readonly."""
        source = {"path": "/data", "readonly": "yes"}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "readonly" in str(exc_info.value).lower()


class TestValidateRuleConfig:
    """Tests for validate_rule_config function."""

    def test_valid_minimal_rule(self):
        """Test minimal valid rule."""
        rule = {"type": "exclude", "pattern": "*.tmp"}
        assert validate_rule_config(rule) == True

    def test_valid_full_rule(self):
        """Test fully populated rule."""
        rule = {
            "type": "include",
            "pattern": "*.py",
            "name": "Python files",
            "priority": 100,
            "conditions": {"min_size": 1024},
        }
        assert validate_rule_config(rule) == True

    def test_invalid_rule_missing_type(self):
        """Test rule without type."""
        rule = {"pattern": "*.tmp"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "type" in str(exc_info.value).lower()

    def test_invalid_rule_bad_type(self):
        """Test rule with invalid type."""
        rule = {"type": "invalid", "pattern": "*.tmp"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "type" in str(exc_info.value).lower()

    def test_invalid_rule_missing_pattern(self):
        """Test rule without pattern."""
        rule = {"type": "exclude"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "pattern" in str(exc_info.value).lower()

    def test_invalid_rule_bad_pattern(self):
        """Test rule with invalid pattern."""
        rule = {"type": "exclude", "pattern": ""}
        with pytest.raises(ValidationError):
            validate_rule_config(rule)

    def test_invalid_rule_bad_priority(self):
        """Test rule with invalid priority."""
        rule = {"type": "exclude", "pattern": "*.tmp", "priority": "high"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "priority" in str(exc_info.value).lower()


class TestValidateTransformConfig:
    """Tests for validate_transform_config function."""

    def test_valid_minimal_transform(self):
        """Test minimal valid transform."""
        transform = {"type": "compress", "pattern": "*.txt"}
        assert validate_transform_config(transform) == True

    def test_valid_full_transform(self):
        """Test fully populated transform."""
        transform = {
            "type": "convert",
            "from": "markdown",
            "to": "html",
            "pattern": "*.md",
            "name": "MD to HTML",
            "options": {"theme": "github"},
        }
        assert validate_transform_config(transform) == True

    def test_invalid_transform_missing_type(self):
        """Test transform without type."""
        transform = {"pattern": "*.md"}
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config(transform)
        assert "type" in str(exc_info.value).lower()

    def test_invalid_transform_bad_type(self):
        """Test transform with invalid type."""
        transform = {"type": "invalid", "pattern": "*.txt"}
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config(transform)
        assert "type" in str(exc_info.value).lower()

    def test_invalid_transform_missing_pattern(self):
        """Test transform without pattern."""
        transform = {"type": "compress"}
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config(transform)
        assert "pattern" in str(exc_info.value).lower()

    def test_invalid_transform_bad_pattern(self):
        """Test transform with invalid pattern."""
        transform = {"type": "compress", "pattern": ""}
        with pytest.raises(ValidationError):
            validate_transform_config(transform)


class TestValidateVirtualLayerConfig:
    """Tests for validate_virtual_layer_config function."""

    def test_valid_minimal_layer(self):
        """Test minimal valid virtual layer."""
        layer = {"name": "by-type", "type": "classifier"}
        assert validate_virtual_layer_config(layer) == True

    def test_valid_full_layer(self):
        """Test fully populated virtual layer."""
        layer = {
            "name": "by-date",
            "type": "date",
            "date_field": "mtime",
            "format": "%Y/%m/%d",
            "enabled": True,
        }
        assert validate_virtual_layer_config(layer) == True

    def test_invalid_layer_missing_name(self):
        """Test layer without name."""
        layer = {"type": "classifier"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "name" in str(exc_info.value).lower()

    def test_invalid_layer_bad_name(self):
        """Test layer with invalid name."""
        layer = {"name": "invalid name!", "type": "classifier"}
        with pytest.raises(ValidationError):
            validate_virtual_layer_config(layer)

    def test_invalid_layer_missing_type(self):
        """Test layer without type."""
        layer = {"name": "by-type"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "type" in str(exc_info.value).lower()

    def test_invalid_layer_bad_type(self):
        """Test layer with invalid type."""
        layer = {"name": "by-type", "type": "invalid"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "type" in str(exc_info.value).lower()


class TestValidateCacheConfig:
    """Tests for validate_cache_config function."""

    def test_valid_minimal_cache(self):
        """Test minimal valid cache config."""
        cache = {"enabled": True}
        assert validate_cache_config(cache) == True

    def test_valid_full_cache(self):
        """Test fully populated cache config."""
        cache = {"enabled": True, "max_size_mb": 1024, "ttl_seconds": 300, "eviction_policy": "lru"}
        assert validate_cache_config(cache) == True

    def test_valid_disabled_cache(self):
        """Test disabled cache config."""
        cache = {"enabled": False}
        assert validate_cache_config(cache) == True

    def test_invalid_cache_bad_enabled(self):
        """Test cache with non-boolean enabled."""
        cache = {"enabled": "yes"}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "enabled" in str(exc_info.value).lower()

    def test_invalid_cache_bad_size(self):
        """Test cache with invalid size."""
        cache = {"enabled": True, "max_size_mb": -100}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "max_size_mb" in str(exc_info.value).lower()

    def test_invalid_cache_bad_ttl(self):
        """Test cache with invalid TTL."""
        cache = {"enabled": True, "ttl_seconds": -1}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "ttl" in str(exc_info.value).lower()


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_absolute_path(self):
        """Test valid absolute path."""
        assert validate_path("/data/files") == True

    def test_valid_relative_path(self):
        """Test valid relative path."""
        assert validate_path("./data/files") == True

    def test_valid_home_path(self):
        """Test valid home path."""
        assert validate_path("~/documents") == True

    def test_invalid_empty_path(self):
        """Test empty path."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_path_traversal(self):
        """Test path with traversal."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path("/data/../../../etc/passwd")
        assert "traversal" in str(exc_info.value).lower()

    def test_invalid_null_bytes(self):
        """Test path with null bytes."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path("/data/file\x00.txt")
        assert "null" in str(exc_info.value).lower()


class TestValidatePattern:
    """Tests for validate_pattern function."""

    def test_valid_glob_pattern(self):
        """Test valid glob pattern."""
        assert validate_pattern("*.py") == True
        assert validate_pattern("**/*.txt") == True

    def test_valid_complex_pattern(self):
        """Test complex glob pattern."""
        assert validate_pattern("src/**/*.[ch]") == True

    def test_invalid_empty_pattern(self):
        """Test empty pattern."""
        with pytest.raises(ValidationError) as exc_info:
            validate_pattern("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_null_bytes(self):
        """Test pattern with null bytes."""
        with pytest.raises(ValidationError) as exc_info:
            validate_pattern("*.txt\x00")
        assert "invalid" in str(exc_info.value).lower()


class TestValidateLayerName:
    """Tests for validate_layer_name function."""

    def test_valid_layer_names(self):
        """Test valid layer names."""
        assert validate_layer_name("by-type") == True
        assert validate_layer_name("by_date") == True
        assert validate_layer_name("layer123") == True

    def test_invalid_empty_name(self):
        """Test empty layer name."""
        with pytest.raises(ValidationError) as exc_info:
            validate_layer_name("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_special_chars(self):
        """Test layer name with special characters."""
        with pytest.raises(ValidationError) as exc_info:
            validate_layer_name("layer/name")
        assert "invalid" in str(exc_info.value).lower()

    def test_invalid_spaces(self):
        """Test layer name with spaces."""
        with pytest.raises(ValidationError) as exc_info:
            validate_layer_name("layer name")
        assert "invalid" in str(exc_info.value).lower()


class TestValidateVersion:
    """Tests for validate_version function."""

    def test_valid_versions(self):
        """Test valid version strings."""
        assert validate_version("1.0") == True
        assert validate_version("2.1.3") == True
        assert validate_version("0.0.1") == True

    def test_invalid_empty_version(self):
        """Test empty version."""
        with pytest.raises(ValidationError) as exc_info:
            validate_version("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_format(self):
        """Test invalid version format."""
        with pytest.raises(ValidationError) as exc_info:
            validate_version("v1.0")
        assert "format" in str(exc_info.value).lower()

    def test_invalid_non_numeric(self):
        """Test non-numeric version."""
        with pytest.raises(ValidationError) as exc_info:
            validate_version("one.zero")
        assert "format" in str(exc_info.value).lower()


class TestValidatePort:
    """Tests for validate_port function."""

    def test_valid_ports(self):
        """Test valid port numbers."""
        assert validate_port(80) == True
        assert validate_port("8080") == True
        assert validate_port(65535) == True

    def test_invalid_low_port(self):
        """Test port below valid range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port(0)
        assert "1-65535" in str(exc_info.value)

    def test_invalid_high_port(self):
        """Test port above valid range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port(65536)
        assert "1-65535" in str(exc_info.value)

    def test_invalid_negative_port(self):
        """Test negative port."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port(-1)
        assert "1-65535" in str(exc_info.value)

    def test_invalid_string_port(self):
        """Test non-numeric string port."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port("http")
        assert "numeric" in str(exc_info.value).lower()


class TestValidateFileSize:
    """Tests for validate_file_size function."""

    def test_valid_sizes(self):
        """Test valid file sizes."""
        assert validate_file_size(0) == True
        assert validate_file_size(1024) == True
        assert validate_file_size(1.5e9) == True

    def test_invalid_negative_size(self):
        """Test negative file size."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(-1)
        assert "negative" in str(exc_info.value).lower()

    def test_invalid_huge_size(self):
        """Test file size exceeding limit."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(1e15)  # 1 PB
        assert "exceeds" in str(exc_info.value).lower()

    def test_invalid_non_numeric(self):
        """Test non-numeric size."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size("1MB")
        assert "numeric" in str(exc_info.value).lower()


class TestValidatePermissions:
    """Tests for validate_permissions function."""

    def test_valid_octal_permissions(self):
        """Test valid octal permissions."""
        assert validate_permissions(0o644) == True
        assert validate_permissions(0o755) == True
        assert validate_permissions(0o777) == True

    def test_valid_string_permissions(self):
        """Test valid string octal permissions."""
        assert validate_permissions("644") == True
        assert validate_permissions("755") == True

    def test_invalid_permissions_too_high(self):
        """Test permissions exceeding octal range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions(0o1000)
        assert "0-777" in str(exc_info.value)

    def test_invalid_permissions_negative(self):
        """Test negative permissions."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions(-1)
        assert "0-777" in str(exc_info.value)

    def test_invalid_string_permissions(self):
        """Test invalid string permissions."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions("rwxr-xr-x")
        assert "octal" in str(exc_info.value).lower()


class TestValidateRegex:
    """Tests for validate_regex function."""

    def test_valid_regex(self):
        """Test valid regex patterns."""
        pattern = validate_regex(r"^\d+$")
        assert isinstance(pattern, re.Pattern)
        assert pattern.match("123")

    def test_valid_complex_regex(self):
        """Test complex regex pattern."""
        pattern = validate_regex(r"(?P<name>\w+)@(?P<domain>[\w.]+)")
        assert isinstance(pattern, re.Pattern)
        match = pattern.match("user@example.com")
        assert match.group("name") == "user"

    def test_invalid_empty_regex(self):
        """Test empty regex."""
        with pytest.raises(ValidationError) as exc_info:
            validate_regex("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_malformed_regex(self):
        """Test malformed regex pattern."""
        with pytest.raises(ValidationError) as exc_info:
            validate_regex(r"[unclosed")
        assert "compile" in str(exc_info.value).lower()


class TestValidateGlob:
    """Tests for validate_glob function."""

    def test_valid_glob_patterns(self):
        """Test valid glob patterns."""
        assert validate_glob("*.txt") == True
        assert validate_glob("**/*.py") == True
        assert validate_glob("[abc]*.log") == True

    def test_valid_complex_glob(self):
        """Test complex glob pattern."""
        assert validate_glob("src/**/test_*.py[co]") == True

    def test_invalid_empty_glob(self):
        """Test empty glob pattern."""
        with pytest.raises(ValidationError) as exc_info:
            validate_glob("")
        assert "empty" in str(exc_info.value).lower()

    def test_invalid_null_glob(self):
        """Test glob with null bytes."""
        with pytest.raises(ValidationError) as exc_info:
            validate_glob("*.txt\x00")
        assert "invalid" in str(exc_info.value).lower()


class TestValidateTimeout:
    """Tests for validate_timeout function."""

    def test_valid_timeouts(self):
        """Test valid timeout values."""
        assert validate_timeout(1) == True
        assert validate_timeout(30.5) == True
        assert validate_timeout(3600) == True

    def test_invalid_zero_timeout(self):
        """Test zero timeout."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(0)
        assert "positive" in str(exc_info.value).lower()

    def test_invalid_negative_timeout(self):
        """Test negative timeout."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(-1)
        assert "positive" in str(exc_info.value).lower()

    def test_invalid_huge_timeout(self):
        """Test timeout exceeding limit."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(100000)  # Over 24 hours
        assert "exceeds" in str(exc_info.value).lower()

    def test_invalid_non_numeric_timeout(self):
        """Test non-numeric timeout."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout("30s")
        assert "numeric" in str(exc_info.value).lower()
