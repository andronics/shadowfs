#!/usr/bin/env python3
"""Complete test coverage for validators.py module."""

import re
from unittest.mock import MagicMock, patch

import pytest

from shadowfs.foundation.constants import ErrorCode
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


class TestValidationErrorComplete:
    """Complete tests for ValidationError."""

    def test_error_code_property(self):
        """Test error_code property access."""
        error = ValidationError("Test", error_code=ErrorCode.INVALID_INPUT)
        assert error.error_code == ErrorCode.INVALID_INPUT


class TestValidateConfigComplete:
    """Complete tests for validate_config."""

    def test_config_not_dict(self):
        """Test config that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_config_invalid_version(self):
        """Test config with invalid version format."""
        config = {"version": "invalid"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "version" in str(exc_info.value).lower()

    def test_config_sources_not_list(self):
        """Test config with sources that's not a list."""
        config = {"version": "1.0", "sources": "not a list"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "sources must be a list" in str(exc_info.value).lower()

    def test_config_invalid_source_in_list(self):
        """Test config with invalid source in list."""
        config = {"version": "1.0", "sources": [{"path": "/valid"}, {"no_path": "invalid"}]}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "source" in str(exc_info.value).lower()

    def test_config_rules_not_list(self):
        """Test config with rules that's not a list."""
        config = {"version": "1.0", "rules": "not a list"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "rules must be a list" in str(exc_info.value).lower()

    def test_config_invalid_rule_in_list(self):
        """Test config with invalid rule in list."""
        config = {
            "version": "1.0",
            "rules": [{"type": "exclude", "pattern": "*.tmp"}, {"no_type": "invalid"}],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "rule" in str(exc_info.value).lower()

    def test_config_transforms_not_list(self):
        """Test config with transforms that's not a list."""
        config = {"version": "1.0", "transforms": "not a list"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "transforms must be a list" in str(exc_info.value).lower()

    def test_config_invalid_transform_in_list(self):
        """Test config with invalid transform in list."""
        config = {
            "version": "1.0",
            "transforms": [{"type": "compress", "pattern": "*.txt"}, {"no_type": "invalid"}],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "transform" in str(exc_info.value).lower()

    def test_config_layers_not_list(self):
        """Test config with virtual_layers that's not a list."""
        config = {"version": "1.0", "virtual_layers": "not a list"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "virtual layers must be a list" in str(exc_info.value).lower()

    def test_config_invalid_layer_in_list(self):
        """Test config with invalid virtual layer in list."""
        config = {
            "version": "1.0",
            "virtual_layers": [{"name": "valid", "type": "classifier"}, {"no_name": "invalid"}],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "layer" in str(exc_info.value).lower()

    def test_config_invalid_cache(self):
        """Test config with invalid cache that raises exception."""
        config = {
            "version": "1.0",
            "cache": {"enabled": "not_bool"},  # Will cause cache validation to fail
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "cache" in str(exc_info.value).lower()


class TestValidateSourceConfigComplete:
    """Complete tests for validate_source_config."""

    def test_source_not_dict(self):
        """Test source that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_source_invalid_priority_type(self):
        """Test source with non-integer priority."""
        source = {"path": "/data", "priority": "high"}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "non-negative integer" in str(exc_info.value).lower()

    def test_source_priority_negative(self):
        """Test source with negative priority."""
        source = {"path": "/data", "priority": -5}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "non-negative integer" in str(exc_info.value).lower()

    def test_source_readonly_not_bool(self):
        """Test source with non-boolean readonly."""
        source = {"path": "/data", "readonly": 1}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "boolean" in str(exc_info.value).lower()

    def test_source_invalid_path(self):
        """Test source with invalid path - empty."""
        source = {"path": ""}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "empty" in str(exc_info.value).lower()


class TestValidateRuleConfigComplete:
    """Complete tests for validate_rule_config."""

    def test_rule_not_dict(self):
        """Test rule that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_rule_priority_not_int(self):
        """Test rule with non-integer priority."""
        rule = {"type": "exclude", "pattern": "*.tmp", "priority": "low"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "priority must be integer" in str(exc_info.value).lower()

    def test_rule_invalid_pattern(self):
        """Test rule with invalid pattern."""
        rule = {"type": "exclude", "pattern": "pattern\x00null"}
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "pattern" in str(exc_info.value).lower()


class TestValidateTransformConfigComplete:
    """Complete tests for validate_transform_config."""

    def test_transform_not_dict(self):
        """Test transform that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_transform_invalid_pattern(self):
        """Test transform with invalid pattern."""
        transform = {"type": "compress", "pattern": "\x00null"}
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config(transform)
        assert "pattern" in str(exc_info.value).lower()


class TestValidateVirtualLayerConfigComplete:
    """Complete tests for validate_virtual_layer_config."""

    def test_layer_not_dict(self):
        """Test layer that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_layer_invalid_name(self):
        """Test layer with invalid name."""
        layer = {"name": "invalid/name", "type": "classifier"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "name" in str(exc_info.value).lower()

    def test_layer_enabled_not_bool(self):
        """Test layer with non-boolean enabled field."""
        layer = {"name": "by-type", "type": "classifier", "enabled": "yes"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "enabled must be boolean" in str(exc_info.value).lower()


class TestValidateCacheConfigComplete:
    """Complete tests for validate_cache_config."""

    def test_cache_not_dict(self):
        """Test cache that's not a dictionary."""
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config("not a dict")
        assert "dictionary" in str(exc_info.value).lower()

    def test_cache_missing_enabled(self):
        """Test cache without enabled field."""
        cache = {"max_size_mb": 512}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "enabled" in str(exc_info.value).lower()

    def test_cache_enabled_not_bool(self):
        """Test cache with non-boolean enabled."""
        cache = {"enabled": "true"}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "enabled must be boolean" in str(exc_info.value).lower()

    def test_cache_size_not_int(self):
        """Test cache with non-integer size."""
        cache = {"enabled": True, "max_size_mb": "large"}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "size must be integer" in str(exc_info.value).lower()

    def test_cache_size_negative(self):
        """Test cache with negative size."""
        cache = {"enabled": True, "max_size_mb": -512}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "size must be positive" in str(exc_info.value).lower()

    def test_cache_ttl_not_int(self):
        """Test cache with non-integer TTL."""
        cache = {"enabled": True, "ttl_seconds": "long"}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "ttl must be integer" in str(exc_info.value).lower()

    def test_cache_ttl_negative(self):
        """Test cache with negative TTL."""
        cache = {"enabled": True, "ttl_seconds": -300}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "ttl must be positive" in str(exc_info.value).lower()


class TestValidatePathComplete:
    """Complete tests for validate_path."""

    def test_path_not_string(self):
        """Test path that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path(123)
        assert "string" in str(exc_info.value).lower()

    def test_path_with_null_bytes(self):
        """Test path with null bytes."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path("/data/file\x00.txt")
        assert "null" in str(exc_info.value).lower()

    def test_path_with_control_chars(self):
        """Test path with control characters."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path("/data/file\x01.txt")
        assert "control" in str(exc_info.value).lower()


class TestValidatePatternComplete:
    """Complete tests for validate_pattern."""

    def test_pattern_not_string(self):
        """Test pattern that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_pattern(123)
        assert "string" in str(exc_info.value).lower()

    def test_pattern_with_control_chars(self):
        """Test pattern with control characters."""
        bad_patterns = [
            "pattern\x00null",
            "pattern\x01",
            "pattern\x7f",
        ]
        for pattern in bad_patterns:
            with pytest.raises(ValidationError) as exc_info:
                validate_pattern(pattern)
            assert "invalid" in str(exc_info.value).lower()


class TestValidateLayerNameComplete:
    """Complete tests for validate_layer_name."""

    def test_layer_name_not_string(self):
        """Test layer name that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_layer_name(123)
        assert "string" in str(exc_info.value).lower()

    def test_layer_name_invalid_chars(self):
        """Test layer name with invalid characters."""
        bad_names = [
            "layer/name",
            "layer name",
            "layer\\name",
            "layer:name",
            "layer|name",
        ]
        for name in bad_names:
            with pytest.raises(ValidationError) as exc_info:
                validate_layer_name(name)
            assert "invalid" in str(exc_info.value).lower()


class TestValidateVersionComplete:
    """Complete tests for validate_version."""

    def test_version_not_string(self):
        """Test version that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_version(1.0)
        assert "string" in str(exc_info.value).lower()

    def test_version_invalid_format(self):
        """Test version with invalid format."""
        bad_versions = [
            "v1.0.0",
            "1.a.0",
            "1..0",
            "1.0.0.0.0",
        ]
        for version in bad_versions:
            with pytest.raises(ValidationError) as exc_info:
                validate_version(version)
            assert "format" in str(exc_info.value).lower()


class TestValidatePortComplete:
    """Complete tests for validate_port."""

    def test_port_string_valid(self):
        """Test valid port as string."""
        assert validate_port("8080") == True

    def test_port_type_error(self):
        """Test port with wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port([8080])
        assert "integer" in str(exc_info.value).lower()

    def test_port_string_non_numeric(self):
        """Test non-numeric string port."""
        with pytest.raises(ValidationError) as exc_info:
            validate_port("abc")
        assert "integer" in str(exc_info.value).lower()

    def test_port_boundaries(self):
        """Test port at boundaries."""
        assert validate_port(1) == True
        assert validate_port(65535) == True

        with pytest.raises(ValidationError):
            validate_port(0)

        with pytest.raises(ValidationError):
            validate_port(65536)


class TestValidateFileSizeComplete:
    """Complete tests for validate_file_size."""

    def test_size_wrong_type(self):
        """Test size with wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size("1MB")
        assert "number" in str(exc_info.value).lower()

    def test_size_float_valid(self):
        """Test valid float size."""
        assert validate_file_size(1024.5) == True

    def test_size_negative(self):
        """Test negative size."""
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(-100)
        assert "negative" in str(exc_info.value).lower()

    def test_size_exceeds_max(self):
        """Test size exceeding maximum."""
        # Assuming MAX_FILE_SIZE is 10GB (10737418240)
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(10737418241)
        assert "exceeds" in str(exc_info.value).lower()


class TestValidatePermissionsComplete:
    """Complete tests for validate_permissions."""

    def test_permissions_string_valid(self):
        """Test valid permissions as string."""
        assert validate_permissions("755") == True
        assert validate_permissions("644") == True

    def test_permissions_wrong_type(self):
        """Test permissions with wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions([755])
        assert "integer or string" in str(exc_info.value).lower()

    def test_permissions_string_non_octal(self):
        """Test non-octal string permissions."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions("abc")
        assert "octal" in str(exc_info.value).lower()

    def test_permissions_out_of_range(self):
        """Test permissions out of valid range."""
        with pytest.raises(ValidationError) as exc_info:
            validate_permissions(1000)
        assert "0-777" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validate_permissions(-1)
        assert "0-777" in str(exc_info.value)


class TestValidateRegexComplete:
    """Complete tests for validate_regex."""

    def test_regex_not_string(self):
        """Test regex that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_regex(123)
        assert "string" in str(exc_info.value).lower()

    def test_regex_compile_error(self):
        """Test regex that doesn't compile."""
        with pytest.raises(ValidationError) as exc_info:
            validate_regex("[unclosed")
        assert "compile" in str(exc_info.value).lower()

    def test_regex_valid_complex(self):
        """Test valid complex regex."""
        pattern = validate_regex(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")
        assert isinstance(pattern, re.Pattern)
        match = pattern.match("2024-11-11")
        assert match.group("year") == "2024"


class TestValidateGlobComplete:
    """Complete tests for validate_glob."""

    def test_glob_not_string(self):
        """Test glob that's not a string."""
        with pytest.raises(ValidationError) as exc_info:
            validate_glob(123)
        assert "string" in str(exc_info.value).lower()

    def test_glob_with_null(self):
        """Test glob with null byte."""
        with pytest.raises(ValidationError) as exc_info:
            validate_glob("*.txt\x00")
        assert "invalid" in str(exc_info.value).lower()

    def test_glob_valid_patterns(self):
        """Test various valid glob patterns."""
        patterns = [
            "*.txt",
            "**/*.py",
            "[!.]*.log",
            "src/**/test_*.py[co]",
            "{*.txt,*.md}",
        ]
        for pattern in patterns:
            assert validate_glob(pattern) == True


class TestValidateTimeoutComplete:
    """Complete tests for validate_timeout."""

    def test_timeout_wrong_type(self):
        """Test timeout with wrong type."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout("30s")
        assert "number" in str(exc_info.value).lower()

    def test_timeout_float_valid(self):
        """Test valid float timeout."""
        assert validate_timeout(30.5) == True

    def test_timeout_zero_or_negative(self):
        """Test zero or negative timeout."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(0)
        assert "positive" in str(exc_info.value).lower()

        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(-10)
        assert "positive" in str(exc_info.value).lower()

    def test_timeout_exceeds_max(self):
        """Test timeout exceeding maximum."""
        # Assuming MAX_TIMEOUT is 86400 (24 hours)
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(86401)
        assert "exceeds" in str(exc_info.value).lower()
