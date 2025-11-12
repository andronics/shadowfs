"""Edge case tests for validators to improve coverage.

This module tests error paths and edge cases in the validation functions.
"""
import pytest

from shadowfs.core.constants import ConfigKey
from shadowfs.core.validators import (
    ValidationError,
    validate_cache_config,
    validate_config,
    validate_pattern,
    validate_rule_config,
    validate_source_config,
    validate_transform_config,
    validate_version,
    validate_virtual_layer_config,
)


class TestValidateConfigErrorPaths:
    """Test error paths in validate_config."""

    def test_config_with_invalid_version_format(self):
        """Test config with invalid version that fails validate_version."""
        config = {"version": "invalid.version.format.too.many.parts"}
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "invalid version format" in str(exc_info.value).lower()

    def test_config_with_invalid_source_at_index(self):
        """Test config with invalid source that fails validate_source_config."""
        config = {
            "version": "1.0",
            "sources": [
                {"path": "/valid/path"},
                {"missing_path_key": "invalid"},  # Missing required 'path' field
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "source" in str(exc_info.value).lower()

    def test_config_with_invalid_rule_at_index(self):
        """Test config with invalid rule that fails validate_rule_config."""
        config = {
            "version": "1.0",
            "rules": [
                {"type": "include", "pattern": "*.py"},
                {"missing_type": "invalid"},  # Missing required 'type' field
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "rule" in str(exc_info.value).lower()

    def test_config_with_invalid_transform_at_index(self):
        """Test config with invalid transform that fails validate_transform_config."""
        config = {
            "version": "1.0",
            "transforms": [
                {"type": "template", "pattern": "*.md"},
                {"missing_type": "invalid"},  # Missing required 'type' field
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "transform" in str(exc_info.value).lower()

    def test_config_with_invalid_virtual_layer_at_index(self):
        """Test config with invalid virtual layer that fails validate_virtual_layer_config."""
        config = {
            "version": "1.0",
            "virtual_layers": [
                {"name": "by-type", "type": "classifier"},
                {"missing_name": "invalid"},  # Missing required 'name' field
            ],
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "virtual layer" in str(exc_info.value).lower()

    def test_config_with_invalid_cache_config(self):
        """Test config with invalid cache that fails validate_cache_config."""
        config = {
            "version": "1.0",
            "cache": {
                "unknown_field": "value",  # Unknown cache field
            },
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_config(config)
        assert "cache" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()


class TestValidateSourceConfigEdgeCases:
    """Edge case tests for validate_source_config."""

    def test_source_with_invalid_path_traversal(self):
        """Test source with path traversal attempt."""
        source = {"path": "/valid/../../../etc/passwd"}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "traversal" in str(exc_info.value).lower()

    def test_source_with_control_characters(self):
        """Test source path with control characters."""
        source = {"path": "/path/with\x00null"}
        with pytest.raises(ValidationError) as exc_info:
            validate_source_config(source)
        assert "null" in str(exc_info.value).lower() or "control" in str(exc_info.value).lower()


class TestValidateRuleConfigEdgeCases:
    """Edge case tests for validate_rule_config."""

    def test_rule_with_invalid_pattern(self):
        """Test rule with invalid pattern that fails validate_pattern."""
        rule = {"type": "include", "pattern": ""}  # Empty pattern
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "pattern" in str(exc_info.value).lower()

    def test_rule_with_patterns_list_containing_invalid(self):
        """Test rule with patterns list containing an invalid pattern."""
        rule = {
            "type": "include",
            "patterns": ["*.py", "*.txt", ""],  # Last pattern is empty
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_rule_config(rule)
        assert "pattern" in str(exc_info.value).lower()


class TestValidateTransformConfigEdgeCases:
    """Edge case tests for validate_transform_config."""

    def test_transform_with_invalid_pattern(self):
        """Test transform with invalid pattern."""
        transform = {"type": "template", "pattern": "\x00invalid"}
        with pytest.raises(ValidationError) as exc_info:
            validate_transform_config(transform)
        assert "pattern" in str(exc_info.value).lower()


class TestValidateVirtualLayerConfigEdgeCases:
    """Edge case tests for validate_virtual_layer_config."""

    def test_layer_with_invalid_name(self):
        """Test virtual layer with invalid name (starts with number)."""
        layer = {"name": "123invalid", "type": "classifier"}
        with pytest.raises(ValidationError) as exc_info:
            validate_virtual_layer_config(layer)
        assert "name" in str(exc_info.value).lower()


class TestValidateCacheConfigEdgeCases:
    """Edge case tests for validate_cache_config."""

    def test_cache_with_invalid_eviction_policy(self):
        """Test cache with invalid eviction policy."""
        cache = {"enabled": True, "eviction_policy": "invalid_policy"}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "eviction" in str(exc_info.value).lower() or "policy" in str(exc_info.value).lower()

    def test_cache_eviction_policy_not_string(self):
        """Test cache with non-string eviction policy (line 334)."""
        cache = {"enabled": True, "eviction_policy": 123}
        with pytest.raises(ValidationError) as exc_info:
            validate_cache_config(cache)
        assert "eviction policy must be string" in str(exc_info.value).lower()


class TestValidatePatternEdgeCases:
    """Edge case tests for validate_pattern."""

    def test_pattern_with_invalid_regex_prefix(self):
        """Test regex pattern that fails to compile."""
        pattern = "regex:[unclosed"
        with pytest.raises(ValidationError) as exc_info:
            validate_pattern(pattern)
        assert "regex" in str(exc_info.value).lower()


class TestValidatePermissionsEdgeCases:
    """Edge case tests for validate_permissions."""

    def test_permissions_mode_with_0o_prefix(self):
        """Test permissions mode string with 0o prefix (line 542)."""
        from shadowfs.core.validators import validate_permissions

        # Mode string with "0o" prefix should work
        assert validate_permissions("0o644") is True
        assert validate_permissions("0o755") is True
        assert validate_permissions("0o777") is True
