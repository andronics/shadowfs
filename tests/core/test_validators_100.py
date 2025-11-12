#!/usr/bin/env python3
"""Tests to achieve 100% coverage for validators.py - focused on missing lines."""

import re
from unittest.mock import patch

import pytest

from shadowfs.core.constants import ErrorCode, Limits
from shadowfs.core.validators import (
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


class TestMissingCoverage:
    """Tests for missing coverage lines."""

    # Line 55, 59 - validate_version
    def test_version_not_string(self):
        with pytest.raises(ValidationError):
            validate_version(123)

    def test_version_invalid_format(self):
        with pytest.raises(ValidationError):
            validate_version("v1.0.0")

    # Lines 69, 79, 89, 99, 105-107 - config validation branches
    def test_config_invalid_source(self):
        config = {"version": "1.0", "sources": [{"invalid": "no_path"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_config_invalid_rule(self):
        config = {"version": "1.0", "rules": [{"invalid": "no_type"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_config_invalid_transform(self):
        config = {"version": "1.0", "transforms": [{"invalid": "no_type"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_config_invalid_layer(self):
        config = {"version": "1.0", "virtual_layers": [{"invalid": "no_name"}]}
        with pytest.raises(ValidationError):
            validate_config(config)

    def test_config_invalid_cache(self):
        config = {"version": "1.0", "cache": "not_a_dict"}
        with pytest.raises(ValidationError):
            validate_config(config)

    # Lines 131, 136->140, 142->145 - source validation
    def test_source_path_validation_fails(self):
        source = {"path": "\x00null"}
        with pytest.raises(ValidationError):
            validate_source_config(source)

    # Lines 170-172, 179, 182->187, 185, 188-194 - rule validation
    def test_rule_patterns_list(self):
        rule = {"type": "exclude", "patterns": ["*.tmp", "*.bak"]}
        assert validate_rule_config(rule) == True

    def test_rule_patterns_not_list(self):
        rule = {"type": "exclude", "patterns": "*.tmp"}
        with pytest.raises(ValidationError):
            validate_rule_config(rule)

    def test_rule_patterns_invalid_pattern(self):
        rule = {"type": "exclude", "patterns": ["\x00null"]}
        with pytest.raises(ValidationError):
            validate_rule_config(rule)

    def test_rule_no_pattern_or_patterns(self):
        rule = {"type": "exclude"}
        with pytest.raises(ValidationError):
            validate_rule_config(rule)

    def test_rule_invalid_pattern(self):
        rule = {"type": "exclude", "pattern": "\x00null"}
        with pytest.raises(ValidationError):
            validate_rule_config(rule)

    # Lines 212, 221-223, 227, 231 - transform validation
    def test_transform_type_enum_values(self):
        # Test invalid transform type
        transform = {"type": "invalid_type", "pattern": "*.txt"}
        with pytest.raises(ValidationError):
            validate_transform_config(transform)

    def test_transform_pattern_validation_fails(self):
        transform = {"type": "compress", "pattern": "\x00null"}
        with pytest.raises(ValidationError):
            validate_transform_config(transform)

    # Lines 249, 257, 261, 266-268 - virtual layer validation
    def test_layer_type_enum_values(self):
        layer = {"name": "test", "type": "invalid_type"}
        with pytest.raises(ValidationError):
            validate_virtual_layer_config(layer)

    def test_layer_name_validation_fails(self):
        layer = {"name": "invalid/name", "type": "classifier"}
        with pytest.raises(ValidationError):
            validate_virtual_layer_config(layer)

    # Lines 286, 295-306 - cache validation
    def test_cache_size_not_int(self):
        cache = {"enabled": True, "max_size_mb": "large"}
        with pytest.raises(ValidationError):
            validate_cache_config(cache)

    def test_cache_size_negative(self):
        cache = {"enabled": True, "max_size_mb": -100}
        with pytest.raises(ValidationError):
            validate_cache_config(cache)

    def test_cache_ttl_not_int(self):
        cache = {"enabled": True, "ttl_seconds": "long"}
        with pytest.raises(ValidationError):
            validate_cache_config(cache)

    def test_cache_ttl_negative(self):
        cache = {"enabled": True, "ttl_seconds": -1}
        with pytest.raises(ValidationError):
            validate_cache_config(cache)

    # Lines 325, 329, 333, 337 - path validation
    def test_path_not_string(self):
        with pytest.raises(ValidationError):
            validate_path(None)

    def test_path_too_long(self):
        long_path = "a" * (Limits.MAX_PATH_LENGTH + 1)
        with pytest.raises(ValidationError):
            validate_path(long_path)

    def test_path_null_bytes(self):
        with pytest.raises(ValidationError):
            validate_path("/path\x00null")

    def test_path_control_chars(self):
        with pytest.raises(ValidationError):
            validate_path("/path\x01control")

    # Lines 355, 358, 362, 366-370 - pattern validation
    def test_pattern_not_string(self):
        with pytest.raises(ValidationError):
            validate_pattern(None)

    def test_pattern_too_long(self):
        long_pattern = "*" * (Limits.MAX_PATH_LENGTH + 1)
        with pytest.raises(ValidationError):
            validate_pattern(long_pattern)

    def test_pattern_null_bytes(self):
        with pytest.raises(ValidationError):
            validate_pattern("*.txt\x00")

    def test_pattern_control_chars(self):
        with pytest.raises(ValidationError):
            validate_pattern("*.txt\x01")

    # Lines 388, 391, 395, 401 - layer name validation
    def test_layer_name_not_string(self):
        with pytest.raises(ValidationError):
            validate_layer_name(None)

    def test_layer_name_too_long(self):
        long_name = "a" * 256
        with pytest.raises(ValidationError):
            validate_layer_name(long_name)

    def test_layer_name_invalid_chars(self):
        with pytest.raises(ValidationError):
            validate_layer_name("name/with/slashes")

    def test_layer_name_valid(self):
        assert validate_layer_name("valid-name_123") == True

    # Lines 419, 422 - version validation
    def test_version_not_str(self):
        with pytest.raises(ValidationError):
            validate_version(None)

    def test_version_bad_format(self):
        with pytest.raises(ValidationError):
            validate_version("not.valid")

    # Lines 443-451 - port validation
    def test_port_not_numeric(self):
        with pytest.raises(ValidationError):
            validate_port(None)

    def test_port_string_invalid(self):
        with pytest.raises(ValidationError):
            validate_port("not_a_number")

    def test_port_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_port(0)
        with pytest.raises(ValidationError):
            validate_port(65536)

    # Lines 466-475 - file size validation
    def test_size_not_numeric(self):
        with pytest.raises(ValidationError):
            validate_file_size("not_a_number")

    def test_size_negative(self):
        with pytest.raises(ValidationError):
            validate_file_size(-1)

    def test_size_too_large(self):
        with pytest.raises(ValidationError):
            validate_file_size(Limits.MAX_FILE_SIZE + 1)

    # Lines 490-506 - permissions validation
    def test_permissions_not_int_or_str(self):
        with pytest.raises(ValidationError):
            validate_permissions(None)

    def test_permissions_string_invalid(self):
        with pytest.raises(ValidationError):
            validate_permissions("not_octal")

    def test_permissions_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_permissions(-1)
        with pytest.raises(ValidationError):
            validate_permissions(0o1000)

    def test_permissions_string_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_permissions("999")

    # Lines 521-527 - regex validation
    def test_regex_not_string(self):
        with pytest.raises(ValidationError):
            validate_regex(None)

    def test_regex_compile_error(self):
        with pytest.raises(ValidationError):
            validate_regex("[unclosed")

    # Lines 542-556 - glob validation
    def test_glob_not_string(self):
        with pytest.raises(ValidationError):
            validate_glob(None)

    def test_glob_too_long(self):
        long_glob = "*" * (Limits.MAX_PATH_LENGTH + 1)
        with pytest.raises(ValidationError):
            validate_glob(long_glob)

    def test_glob_control_chars(self):
        with pytest.raises(ValidationError):
            validate_glob("*.txt\x01")

    # Lines 571-580 - timeout validation
    def test_timeout_not_numeric(self):
        with pytest.raises(ValidationError):
            validate_timeout("not_a_number")

    def test_timeout_zero_or_negative(self):
        with pytest.raises(ValidationError):
            validate_timeout(0)
        with pytest.raises(ValidationError):
            validate_timeout(-1)

    def test_timeout_too_large(self):
        with pytest.raises(ValidationError):
            validate_timeout(Limits.MAX_TIMEOUT + 1)
