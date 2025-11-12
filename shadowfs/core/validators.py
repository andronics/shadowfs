"""
ShadowFS Foundation: Input Validators.

This module provides comprehensive input validation functions for configuration,
paths, patterns, and other user inputs.

Following Meta-Architecture v1.0.0 principles.
"""
import re
from typing import Any, Dict, Pattern, Union

from shadowfs.core.constants import ConfigKey, ErrorCode, LayerType, Limits, RuleType, TransformType


class ValidationError(Exception):
    """Base exception for validation errors."""

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.INVALID_INPUT):
        """Initialize ValidationError.

        Args:
            message: Error message
            error_code: Associated error code
        """
        super().__init__(message)
        self.error_code = error_code


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate ShadowFS configuration structure.

    Args:
        config: Configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ValidationError("Configuration must be a dictionary")

    # Check required version
    if ConfigKey.VERSION not in config:
        raise ValidationError("Configuration must have 'version' field")

    version = config[ConfigKey.VERSION]
    validate_version(version)  # Raises ValidationError on failure

    # Validate sources
    if ConfigKey.SOURCES in config:
        sources = config[ConfigKey.SOURCES]
        if not isinstance(sources, list):
            raise ValidationError("Sources must be a list")

        for i, source in enumerate(sources):
            try:
                validate_source_config(source)
            except ValidationError as e:
                raise ValidationError(f"Invalid source configuration at index {i}: {e}")

    # Validate rules
    if ConfigKey.RULES in config:
        rules = config[ConfigKey.RULES]
        if not isinstance(rules, list):
            raise ValidationError("Rules must be a list")

        for i, rule in enumerate(rules):
            try:
                validate_rule_config(rule)
            except ValidationError as e:
                raise ValidationError(f"Invalid rule configuration at index {i}: {e}")

    # Validate transforms
    if ConfigKey.TRANSFORMS in config:
        transforms = config[ConfigKey.TRANSFORMS]
        if not isinstance(transforms, list):
            raise ValidationError("Transforms must be a list")

        for i, transform in enumerate(transforms):
            try:
                validate_transform_config(transform)
            except ValidationError as e:
                raise ValidationError(f"Invalid transform configuration at index {i}: {e}")

    # Validate virtual layers
    if ConfigKey.VIRTUAL_LAYERS in config:
        layers = config[ConfigKey.VIRTUAL_LAYERS]
        if not isinstance(layers, list):
            raise ValidationError("Virtual layers must be a list")

        for i, layer in enumerate(layers):
            try:
                validate_virtual_layer_config(layer)
            except ValidationError as e:
                raise ValidationError(f"Invalid virtual layer configuration at index {i}: {e}")

    # Validate cache config
    if ConfigKey.CACHE in config:
        cache = config[ConfigKey.CACHE]
        validate_cache_config(cache)  # Raises ValidationError on failure

    return True


def validate_source_config(source: Dict[str, Any]) -> bool:
    """Validate source configuration.

    Args:
        source: Source configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If source is invalid
    """
    if not isinstance(source, dict):
        raise ValidationError("Source must be a dictionary")

    # Required field: path
    if ConfigKey.SOURCE_PATH not in source:
        raise ValidationError("Source must have 'path' field")

    path = source[ConfigKey.SOURCE_PATH]
    if not validate_path(path):
        raise ValidationError(f"Invalid source path: {path}")

    # Optional field: priority (integer)
    if ConfigKey.SOURCE_PRIORITY in source:
        priority = source[ConfigKey.SOURCE_PRIORITY]
        if not isinstance(priority, int) or priority < 0:
            raise ValidationError(f"Source priority must be non-negative integer: {priority}")

    # Optional field: readonly (boolean)
    if ConfigKey.SOURCE_READONLY in source:
        readonly = source[ConfigKey.SOURCE_READONLY]
        if not isinstance(readonly, bool):
            raise ValidationError(f"Source readonly must be boolean: {readonly}")

    return True


def validate_rule_config(rule: Dict[str, Any]) -> bool:
    """Validate rule configuration.

    Args:
        rule: Rule configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If rule is invalid
    """
    if not isinstance(rule, dict):
        raise ValidationError("Rule must be a dictionary")

    # Required field: type
    if ConfigKey.RULE_TYPE not in rule:
        raise ValidationError("Rule must have 'type' field")

    rule_type = rule[ConfigKey.RULE_TYPE]
    try:
        RuleType(rule_type)
    except ValueError:
        valid_types = [t.value for t in RuleType]
        raise ValidationError(f"Invalid rule type: {rule_type}. Must be one of {valid_types}")

    # Must have pattern or patterns
    has_pattern = ConfigKey.RULE_PATTERN in rule
    has_patterns = ConfigKey.RULE_PATTERNS in rule

    if not has_pattern and not has_patterns:
        raise ValidationError("Rule must have 'pattern' or 'patterns' field")

    # Validate pattern(s)
    if has_pattern:
        pattern = rule[ConfigKey.RULE_PATTERN]
        if not validate_pattern(pattern):
            raise ValidationError(f"Invalid pattern: {pattern}")

    if has_patterns:
        patterns = rule[ConfigKey.RULE_PATTERNS]
        if not isinstance(patterns, list):
            raise ValidationError("Patterns must be a list")

        for pattern in patterns:
            if not validate_pattern(pattern):
                raise ValidationError(f"Invalid pattern in list: {pattern}")

    # Optional field: priority (integer)
    if "priority" in rule:
        priority = rule["priority"]
        if not isinstance(priority, int):
            raise ValidationError(f"Rule priority must be integer: {priority}")

    return True


def validate_transform_config(transform: Dict[str, Any]) -> bool:
    """Validate transform configuration.

    Args:
        transform: Transform configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If transform is invalid
    """
    if not isinstance(transform, dict):
        raise ValidationError("Transform must be a dictionary")

    # Required field: type
    if ConfigKey.TRANSFORM_TYPE not in transform:
        raise ValidationError("Transform must have 'type' field")

    transform_type = transform[ConfigKey.TRANSFORM_TYPE]
    try:
        TransformType(transform_type)
    except ValueError:
        valid_types = [t.value for t in TransformType]
        raise ValidationError(
            f"Invalid transform type: {transform_type}. Must be one of {valid_types}"
        )

    # Required field: pattern
    if ConfigKey.TRANSFORM_PATTERN not in transform:
        raise ValidationError("Transform must have 'pattern' field")

    pattern = transform[ConfigKey.TRANSFORM_PATTERN]
    if not validate_pattern(pattern):
        raise ValidationError(f"Invalid transform pattern: {pattern}")

    return True


def validate_virtual_layer_config(layer: Dict[str, Any]) -> bool:
    """Validate virtual layer configuration.

    Args:
        layer: Virtual layer configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If layer is invalid
    """
    if not isinstance(layer, dict):
        raise ValidationError("Virtual layer must be a dictionary")

    # Required field: name
    if "name" not in layer:
        raise ValidationError("Virtual layer must have 'name' field")

    name = layer["name"]
    if not validate_layer_name(name):
        raise ValidationError(f"Invalid virtual layer name: {name}")

    # Required field: type
    if "type" not in layer:
        raise ValidationError("Virtual layer must have 'type' field")

    layer_type = layer["type"]
    try:
        LayerType(layer_type)
    except ValueError:
        valid_types = [t.value for t in LayerType]
        raise ValidationError(
            f"Invalid virtual layer type: {layer_type}. Must be one of {valid_types}"
        )

    # Optional field: enabled (boolean)
    if "enabled" in layer:
        enabled = layer["enabled"]
        if not isinstance(enabled, bool):
            raise ValidationError(f"Layer enabled must be boolean: {enabled}")

    return True


def validate_cache_config(cache: Dict[str, Any]) -> bool:
    """Validate cache configuration.

    Args:
        cache: Cache configuration dictionary

    Returns:
        True if valid

    Raises:
        ValidationError: If cache config is invalid
    """
    if not isinstance(cache, dict):
        raise ValidationError("Cache configuration must be a dictionary")

    # Check for unknown fields
    valid_fields = {
        ConfigKey.CACHE_ENABLED,
        ConfigKey.CACHE_SIZE_MB,
        ConfigKey.CACHE_TTL,
        "eviction_policy",
    }
    unknown_fields = set(cache.keys()) - valid_fields
    if unknown_fields:
        raise ValidationError(f"Unknown cache configuration fields: {', '.join(unknown_fields)}")

    # Optional field: enabled (boolean)
    if ConfigKey.CACHE_ENABLED in cache:
        enabled = cache[ConfigKey.CACHE_ENABLED]
        if not isinstance(enabled, bool):
            raise ValidationError(f"Cache enabled must be boolean: {enabled}")

    # Optional field: size_mb (positive integer)
    if ConfigKey.CACHE_SIZE_MB in cache:
        size_mb = cache[ConfigKey.CACHE_SIZE_MB]
        if not isinstance(size_mb, (int, float)) or size_mb <= 0:
            raise ValidationError(f"Cache max_size_mb must be positive number: {size_mb}")

    # Optional field: ttl_seconds (positive integer)
    if ConfigKey.CACHE_TTL in cache:
        ttl = cache[ConfigKey.CACHE_TTL]
        if not isinstance(ttl, (int, float)) or ttl <= 0:
            raise ValidationError(f"Cache TTL must be positive number: {ttl}")

    # Optional field: eviction_policy (string: lru, lfu, fifo)
    if "eviction_policy" in cache:
        policy = cache["eviction_policy"]
        if not isinstance(policy, str):
            raise ValidationError(f"Cache eviction policy must be string: {policy}")
        valid_policies = {"lru", "lfu", "fifo"}
        if policy not in valid_policies:
            raise ValidationError(
                f"Invalid eviction policy: {policy}. Must be one of {valid_policies}"
            )

    return True


def validate_path(path: str) -> bool:
    """Validate that a path is safe and valid.

    Args:
        path: Path to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If path is invalid
    """
    if not path:
        raise ValidationError("Path cannot be empty")

    if not isinstance(path, str):
        raise ValidationError(f"Path must be string, got {type(path)}")

    # Check length
    if len(path) > Limits.MAX_PATH_LENGTH:
        raise ValidationError(f"Path exceeds maximum length ({Limits.MAX_PATH_LENGTH})")

    # Check for null bytes
    if "\0" in path:
        raise ValidationError("Path contains null bytes")

    # Check for control characters
    if any(ord(c) < 32 and c not in "\t\n\r" for c in path):
        raise ValidationError("Path contains control characters")

    # Check for path traversal attempts
    if ".." in path:
        raise ValidationError("Path traversal not allowed")

    return True


def validate_pattern(pattern: str) -> bool:
    """Validate a glob or regex pattern.

    Args:
        pattern: Pattern to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If pattern is invalid
    """
    if not pattern:
        raise ValidationError("Pattern cannot be empty")

    if not isinstance(pattern, str):
        raise ValidationError(f"Pattern must be string, got {type(pattern)}")

    # Check length
    if len(pattern) > Limits.MAX_PATH_LENGTH:
        raise ValidationError(f"Pattern exceeds maximum length ({Limits.MAX_PATH_LENGTH})")

    # Check for null bytes
    if "\0" in pattern:
        raise ValidationError("Invalid pattern: contains null bytes")

    # Check for control characters
    if any(ord(c) < 32 and c not in "\t\n\r" for c in pattern):
        raise ValidationError("Invalid pattern: contains control characters")

    # Try to compile as regex to check validity
    if pattern.startswith("regex:"):
        regex_pattern = pattern[6:]  # Remove "regex:" prefix
        try:
            re.compile(regex_pattern)
        except re.error as e:
            raise ValidationError(f"Invalid regex pattern: {e}")

    return True


def validate_layer_name(name: str) -> bool:
    """Validate virtual layer name.

    Args:
        name: Layer name to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If name is invalid
    """
    if not name:
        raise ValidationError("Layer name cannot be empty")

    if not isinstance(name, str):
        raise ValidationError(f"Layer name must be string, got {type(name)}")

    # Must be valid directory name
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
        raise ValidationError(
            "Invalid layer name: must start with letter and contain only letters, "
            "numbers, underscore, and hyphen"
        )

    # Check length
    if len(name) > 100:
        raise ValidationError("Layer name exceeds maximum length (100)")

    return True


def validate_version(version: str) -> bool:
    """Validate version string format.

    Args:
        version: Version string to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If version is invalid
    """
    if not version:
        raise ValidationError("Version cannot be empty")

    if not isinstance(version, str):
        raise ValidationError(f"Version must be string, got {type(version)}")

    # Simple semantic version check (X.Y or X.Y.Z)
    if not re.match(r"^\d+\.\d+(\.\d+)?$", version):
        raise ValidationError(f"Invalid version format: {version}. Expected X.Y or X.Y.Z")

    return True


def validate_port(port: Union[int, str]) -> bool:
    """Validate network port number.

    Args:
        port: Port number to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If port is invalid
    """
    try:
        port_num = int(port)
    except (ValueError, TypeError):
        raise ValidationError(f"Port must be numeric, got {type(port)}")

    if port_num < 1 or port_num > 65535:
        raise ValidationError(f"Port must be in range 1-65535, got {port_num}")

    return True


def validate_file_size(size: Union[int, float]) -> bool:
    """Validate file size limit.

    Args:
        size: File size in bytes

    Returns:
        True if valid

    Raises:
        ValidationError: If size is invalid
    """
    if not isinstance(size, (int, float)):
        raise ValidationError(f"Size must be numeric, got {type(size)}")

    if size < 0:
        raise ValidationError(f"Size cannot be negative: {size}")

    if size > Limits.MAX_FILE_SIZE:
        raise ValidationError(f"Size exceeds maximum ({Limits.MAX_FILE_SIZE})")

    return True


def validate_permissions(mode: Union[int, str]) -> bool:
    """Validate file permissions mode.

    Args:
        mode: Permission mode (octal int or string)

    Returns:
        True if valid

    Raises:
        ValidationError: If mode is invalid
    """
    try:
        if isinstance(mode, str):
            # Convert octal string to int
            if mode.startswith("0o"):
                mode_int = int(mode, 8)
            else:
                mode_int = int(mode, 8)
        else:
            mode_int = int(mode)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid permission mode (must be octal): {mode}")

    # Check valid range (0-0777)
    if mode_int < 0 or mode_int > 0o777:
        raise ValidationError(f"Permission mode must be in range 0-777, got: {mode_int:o}")

    return True


def validate_regex(pattern: str) -> Pattern[str]:
    """Validate and compile a regex pattern.

    Args:
        pattern: Regex pattern string

    Returns:
        Compiled regex pattern

    Raises:
        ValidationError: If pattern is invalid
    """
    if not pattern:
        raise ValidationError("Regex pattern cannot be empty")

    try:
        return re.compile(pattern)
    except re.error as e:
        raise ValidationError(f"Failed to compile regex pattern: {e}")


def validate_glob(pattern: str) -> bool:
    """Validate glob pattern.

    Args:
        pattern: Glob pattern string

    Returns:
        True if valid

    Raises:
        ValidationError: If pattern is invalid
    """
    if not pattern:
        raise ValidationError("Glob pattern cannot be empty")

    # Check length
    if len(pattern) > Limits.MAX_PATH_LENGTH:
        raise ValidationError(f"Glob pattern exceeds maximum length ({Limits.MAX_PATH_LENGTH})")

    # Check for null bytes
    if "\0" in pattern:
        raise ValidationError("Invalid glob pattern: contains null bytes")

    # Check for control characters
    if any(ord(c) < 32 and c not in "\t\n\r" for c in pattern):
        raise ValidationError("Invalid glob pattern: contains control characters")

    # Check for invalid glob characters in inappropriate positions
    if pattern.startswith("/") and "**" in pattern:
        parts = pattern.split("/")
        for i, part in enumerate(parts):
            if part == "**" and i not in (0, len(parts) - 1):
                # ** must be alone in its path segment
                if i > 0 and parts[i - 1] != "" and i < len(parts) - 1 and parts[i + 1] != "":
                    pass  # This is valid
            elif "**" in part and part != "**":
                raise ValidationError(f"'**' must be alone in path segment: {part}")

    return True


def validate_timeout(timeout: Union[int, float]) -> bool:
    """Validate timeout value.

    Args:
        timeout: Timeout in seconds

    Returns:
        True if valid

    Raises:
        ValidationError: If timeout is invalid
    """
    if not isinstance(timeout, (int, float)):
        raise ValidationError(f"Timeout must be numeric, got {type(timeout)}")

    if timeout <= 0:
        raise ValidationError(f"Timeout must be positive: {timeout}")

    if timeout > Limits.MAX_TIMEOUT:
        raise ValidationError(f"Timeout exceeds maximum ({Limits.MAX_TIMEOUT} seconds): {timeout}")

    return True
