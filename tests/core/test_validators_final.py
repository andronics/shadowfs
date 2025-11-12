#!/usr/bin/env python3
"""Final tests to maximize validators.py coverage."""

import re

import pytest

from shadowfs.core.constants import ErrorCode, Limits
from shadowfs.core.validators import *


# Test all remaining uncovered lines
def test_validate_config_complete():
    """Complete config validation coverage."""
    # Test non-dict config
    with pytest.raises(ValidationError):
        validate_config("not dict")

    # Test missing version
    with pytest.raises(ValidationError):
        validate_config({})

    # Test invalid version
    with pytest.raises(ValidationError):
        validate_config({"version": "bad"})

    # Test sources not list
    with pytest.raises(ValidationError):
        validate_config({"version": "1.0", "sources": "notlist"})

    # Test rules not list
    with pytest.raises(ValidationError):
        validate_config({"version": "1.0", "rules": "notlist"})

    # Test transforms not list
    with pytest.raises(ValidationError):
        validate_config({"version": "1.0", "transforms": "notlist"})

    # Test virtual_layers not list
    with pytest.raises(ValidationError):
        validate_config({"version": "1.0", "virtual_layers": "notlist"})


def test_validate_source_complete():
    """Complete source validation."""
    # Not dict
    with pytest.raises(ValidationError):
        validate_source_config("notdict")

    # Missing path
    with pytest.raises(ValidationError):
        validate_source_config({})

    # Invalid priority
    with pytest.raises(ValidationError):
        validate_source_config({"path": "/data", "priority": -1})

    # Invalid readonly
    with pytest.raises(ValidationError):
        validate_source_config({"path": "/data", "readonly": "yes"})


def test_validate_rule_complete():
    """Complete rule validation."""
    # Not dict
    with pytest.raises(ValidationError):
        validate_rule_config("notdict")

    # Missing type
    with pytest.raises(ValidationError):
        validate_rule_config({"pattern": "*.txt"})

    # Invalid type
    with pytest.raises(ValidationError):
        validate_rule_config({"type": "badtype", "pattern": "*.txt"})

    # Missing pattern/patterns
    with pytest.raises(ValidationError):
        validate_rule_config({"type": "exclude"})

    # Invalid patterns (not list)
    with pytest.raises(ValidationError):
        validate_rule_config({"type": "exclude", "patterns": "notlist"})

    # Invalid pattern in patterns list
    with pytest.raises(ValidationError):
        validate_rule_config({"type": "exclude", "patterns": ["\x00"]})


def test_validate_transform_complete():
    """Complete transform validation."""
    # Not dict
    with pytest.raises(ValidationError):
        validate_transform_config("notdict")

    # Missing type
    with pytest.raises(ValidationError):
        validate_transform_config({"pattern": "*.txt"})

    # Invalid type
    with pytest.raises(ValidationError):
        validate_transform_config({"type": "badtype", "pattern": "*.txt"})

    # Missing pattern
    with pytest.raises(ValidationError):
        validate_transform_config({"type": "compress"})


def test_validate_virtual_layer_complete():
    """Complete virtual layer validation."""
    # Not dict
    with pytest.raises(ValidationError):
        validate_virtual_layer_config("notdict")

    # Missing name
    with pytest.raises(ValidationError):
        validate_virtual_layer_config({"type": "classifier"})

    # Invalid name
    with pytest.raises(ValidationError):
        validate_layer_name("bad/name")

    # Missing type
    with pytest.raises(ValidationError):
        validate_virtual_layer_config({"name": "test"})

    # Invalid type
    with pytest.raises(ValidationError):
        validate_virtual_layer_config({"name": "test", "type": "badtype"})


def test_validate_cache_complete():
    """Complete cache validation."""
    # Not dict
    with pytest.raises(ValidationError):
        validate_cache_config("notdict")

    # Invalid enabled
    with pytest.raises(ValidationError):
        validate_cache_config({"enabled": "yes"})

    # Invalid size
    with pytest.raises(ValidationError):
        validate_cache_config({"max_size_mb": -1})

    # Invalid TTL
    with pytest.raises(ValidationError):
        validate_cache_config({"ttl_seconds": -1})


def test_validate_path_complete():
    """Complete path validation."""
    # Empty
    with pytest.raises(ValidationError):
        validate_path("")

    # Not string
    with pytest.raises(ValidationError):
        validate_path(123)

    # Too long
    with pytest.raises(ValidationError):
        validate_path("a" * 5000)

    # Null bytes
    with pytest.raises(ValidationError):
        validate_path("path\x00")

    # Control chars
    with pytest.raises(ValidationError):
        validate_path("path\x01")


def test_validate_pattern_complete():
    """Complete pattern validation."""
    # Not string - check this first
    with pytest.raises(ValidationError):
        validate_pattern(123)

    # Empty
    with pytest.raises(ValidationError):
        validate_pattern("")

    # Null bytes
    with pytest.raises(ValidationError):
        validate_pattern("pattern\x00")

    # Regex with error
    with pytest.raises(ValidationError):
        validate_pattern("regex:[unclosed")


def test_validate_layer_name_complete():
    """Complete layer name validation."""
    # Empty
    with pytest.raises(ValidationError):
        validate_layer_name("")

    # Not string
    with pytest.raises(ValidationError):
        validate_layer_name(123)

    # Too long
    with pytest.raises(ValidationError):
        validate_layer_name("a" * 300)

    # Invalid chars
    with pytest.raises(ValidationError):
        validate_layer_name("name/bad")


def test_validate_version_complete():
    """Complete version validation."""
    # Empty
    with pytest.raises(ValidationError):
        validate_version("")

    # Not string
    with pytest.raises(ValidationError):
        validate_version(123)

    # Invalid format
    with pytest.raises(ValidationError):
        validate_version("notvalid")


def test_validate_port_complete():
    """Complete port validation."""
    # Invalid type
    with pytest.raises(ValidationError):
        validate_port([])

    # Out of range
    with pytest.raises(ValidationError):
        validate_port(0)
    with pytest.raises(ValidationError):
        validate_port(70000)

    # String non-numeric
    with pytest.raises(ValidationError):
        validate_port("notnum")


def test_validate_file_size_complete():
    """Complete file size validation."""
    # Wrong type
    with pytest.raises(ValidationError):
        validate_file_size("notnum")

    # Negative
    with pytest.raises(ValidationError):
        validate_file_size(-1)

    # Too large
    with pytest.raises(ValidationError):
        validate_file_size(Limits.MAX_FILE_SIZE + 1)


def test_validate_permissions_complete():
    """Complete permissions validation."""
    # Wrong type
    with pytest.raises(ValidationError):
        validate_permissions([])

    # Out of range
    with pytest.raises(ValidationError):
        validate_permissions(-1)
    with pytest.raises(ValidationError):
        validate_permissions(1000)

    # String invalid
    with pytest.raises(ValidationError):
        validate_permissions("notoctal")

    # String out of range
    with pytest.raises(ValidationError):
        validate_permissions("999")


def test_validate_regex_complete():
    """Complete regex validation."""
    # Empty
    with pytest.raises(ValidationError):
        validate_regex("")

    # Invalid regex
    with pytest.raises(ValidationError):
        validate_regex("[unclosed")

    # Valid regex
    pattern = validate_regex(r"\d+")
    assert pattern.match("123")


def test_validate_glob_complete():
    """Complete glob validation."""
    # Empty
    with pytest.raises(ValidationError):
        validate_glob("")

    # Invalid ** usage
    with pytest.raises(ValidationError):
        validate_glob("/path/**bad/file")

    # Valid glob
    assert validate_glob("*.txt") == True
    assert validate_glob("/path/**/file") == True


def test_validate_timeout_complete():
    """Complete timeout validation."""
    # Wrong type
    with pytest.raises(ValidationError):
        validate_timeout("notnum")

    # Zero or negative
    with pytest.raises(ValidationError):
        validate_timeout(0)
    with pytest.raises(ValidationError):
        validate_timeout(-1)

    # Too large
    with pytest.raises(ValidationError):
        validate_timeout(Limits.MAX_TIMEOUT + 1)
