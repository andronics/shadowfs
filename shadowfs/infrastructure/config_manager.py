#!/usr/bin/env python3
"""Hierarchical configuration manager with hot-reload for ShadowFS.

This module provides configuration management with:
- 6-level precedence hierarchy
- Hot-reload without restart
- Schema validation
- Environment variable substitution
- File watching for changes
- Thread-safe operations
- Merge strategies for nested configs

Example:
    >>> config = ConfigManager()
    >>> config.load_file("shadowfs.yaml")
    >>> config.get("cache.max_size_bytes", default=1024)
    >>> config.watch_file(callback=on_config_change)
"""

import os
import threading
import time
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from shadowfs.foundation.constants import ErrorCode


class ConfigSource(Enum):
    """Configuration source precedence levels."""

    COMPILED_DEFAULTS = 1  # Lowest precedence
    SYSTEM_CONFIG = 2
    USER_CONFIG = 3
    ENVIRONMENT = 4
    CLI_ARGS = 5
    RUNTIME = 6  # Highest precedence


@dataclass
class ConfigValue:
    """Configuration value with metadata."""

    value: Any
    source: ConfigSource
    timestamp: float = field(default_factory=time.time)
    validated: bool = False


class ConfigError(Exception):
    """Configuration error."""

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.INVALID_INPUT):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ConfigManager:
    """Thread-safe hierarchical configuration manager.

    Manages configuration from multiple sources with precedence:
    1. Compiled defaults (lowest)
    2. System config (/etc/shadowfs/config.yaml)
    3. User config (~/.config/shadowfs/config.yaml)
    4. Environment variables (SHADOWFS_*)
    5. CLI arguments
    6. Runtime updates (highest)

    Supports hot-reload, schema validation, and file watching.
    """

    DEFAULT_CONFIG = {
        "shadowfs": {
            "sources": [],
            "cache": {
                "enabled": True,
                "max_size_mb": 512,
                "ttl_seconds": 300,
            },
            "logging": {
                "level": "INFO",
                "file": None,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "metrics": {
                "enabled": True,
                "port": 9090,
            },
            "security": {
                "allow_symlinks": False,
                "max_file_size_mb": 1024,
            },
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration manager.

        Args:
            config_file: Optional config file to load
        """
        self._config: Dict[ConfigSource, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_files: Set[str] = set()
        self._file_mtimes: Dict[str, float] = {}
        self._stop_watching = threading.Event()

        # Initialize with defaults
        self._config[ConfigSource.COMPILED_DEFAULTS] = self.DEFAULT_CONFIG.copy()

        # Load config file if provided
        if config_file:
            self.load_file(config_file)

        # Load environment variables
        self._load_environment()

    def load_file(self, file_path: str, source: ConfigSource = ConfigSource.USER_CONFIG) -> None:
        """Load configuration from YAML file.

        Args:
            file_path: Path to YAML config file
            source: Configuration source level

        Raises:
            ConfigError: If file cannot be loaded or parsed
        """
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise ConfigError(f"Config file not found: {file_path}", ErrorCode.NOT_FOUND)

        try:
            with open(path, 'r') as f:
                config_data = yaml.safe_load(f)

            if not isinstance(config_data, dict):
                raise ConfigError(f"Invalid config format in {file_path}", ErrorCode.INVALID_INPUT)

            with self._lock:
                self._config[source] = config_data
                self._file_mtimes[str(path)] = path.stat().st_mtime

        except yaml.YAMLError as e:
            raise ConfigError(f"YAML parse error in {file_path}: {e}", ErrorCode.INVALID_INPUT)
        except Exception as e:
            raise ConfigError(f"Error loading config {file_path}: {e}", ErrorCode.INTERNAL_ERROR)

    def load_dict(self, config_data: Dict[str, Any], source: ConfigSource = ConfigSource.RUNTIME) -> None:
        """Load configuration from dictionary.

        Args:
            config_data: Configuration dictionary
            source: Configuration source level
        """
        with self._lock:
            self._config[source] = config_data.copy()

    def _load_environment(self) -> None:
        """Load configuration from environment variables.

        Environment variables in format: SHADOWFS_SECTION_KEY=value
        Example: SHADOWFS_CACHE_MAX_SIZE_MB=1024
        """
        env_config = {}

        for key, value in os.environ.items():
            if not key.startswith("SHADOWFS_"):
                continue

            # Remove SHADOWFS_ prefix and split by underscore
            parts = key[9:].lower().split("_")

            # Build nested dictionary
            current = env_config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set value (try to parse as int/float/bool)
            parsed_value = self._parse_env_value(value)
            current[parts[-1]] = parsed_value

        if env_config:
            with self._lock:
                # Wrap in shadowfs key if needed
                if "shadowfs" not in env_config:
                    env_config = {"shadowfs": env_config}
                self._config[ConfigSource.ENVIRONMENT] = env_config

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value.

        Args:
            value: String value from environment

        Returns:
            Parsed value (int, float, bool, or str)
        """
        # Try boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Try int
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Args:
            key: Dot-separated key path (e.g., "shadowfs.cache.max_size_mb")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            # Search from highest to lowest precedence
            for source in sorted(self._config.keys(), key=lambda s: s.value, reverse=True):
                value = self._get_nested(self._config[source], key)
                if value is not None:
                    return value

            return default

    def _get_nested(self, config: Dict[str, Any], key: str) -> Optional[Any]:
        """Get value from nested dictionary using dot notation.

        Args:
            config: Configuration dictionary
            key: Dot-separated key path

        Returns:
            Value or None if not found
        """
        parts = key.split(".")
        current = config

        for part in parts:
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current[part]

        return current

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.RUNTIME) -> None:
        """Set configuration value.

        Args:
            key: Dot-separated key path
            value: Value to set
            source: Configuration source level
        """
        with self._lock:
            if source not in self._config:
                self._config[source] = {}

            # Build nested structure
            parts = key.split(".")
            current = self._config[source]

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

            # Notify watchers
            self._notify_watchers()

    def get_all(self) -> Dict[str, Any]:
        """Get merged configuration from all sources.

        Returns:
            Merged configuration dictionary
        """
        with self._lock:
            merged = {}

            # Merge from lowest to highest precedence
            for source in sorted(self._config.keys(), key=lambda s: s.value):
                merged = self._deep_merge(merged, self._config[source])

            return merged

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def reload(self) -> None:
        """Reload all file-based configurations."""
        with self._lock:
            files_to_reload = list(self._file_mtimes.keys())

        for file_path in files_to_reload:
            try:
                # Determine source based on path
                if "/etc/shadowfs" in file_path:
                    source = ConfigSource.SYSTEM_CONFIG
                else:
                    source = ConfigSource.USER_CONFIG

                self.load_file(file_path, source)
            except ConfigError:
                pass  # Ignore errors during reload

        self._notify_watchers()

    def watch_file(self, file_path: str, interval: float = 1.0) -> None:
        """Watch configuration file for changes.

        Args:
            file_path: Path to file to watch
            interval: Check interval in seconds
        """
        path = Path(file_path).expanduser().resolve()
        file_str = str(path)

        with self._lock:
            self._watch_files.add(file_str)

            if self._watch_thread is None or not self._watch_thread.is_alive():
                self._stop_watching.clear()
                self._watch_thread = threading.Thread(
                    target=self._watch_loop,
                    args=(interval,),
                    daemon=True
                )
                self._watch_thread.start()

    def _watch_loop(self, interval: float) -> None:
        """File watching loop.

        Args:
            interval: Check interval in seconds
        """
        while not self._stop_watching.is_set():
            with self._lock:
                files = list(self._watch_files)

            for file_path in files:
                try:
                    path = Path(file_path)
                    if not path.exists():
                        continue

                    mtime = path.stat().st_mtime
                    old_mtime = self._file_mtimes.get(file_path, 0)

                    if mtime > old_mtime:
                        # File changed, reload
                        if "/etc/shadowfs" in file_path:
                            source = ConfigSource.SYSTEM_CONFIG
                        else:
                            source = ConfigSource.USER_CONFIG

                        self.load_file(file_path, source)
                        self._notify_watchers()

                except Exception:
                    pass  # Ignore errors in watch loop

            time.sleep(interval)

    def stop_watching(self) -> None:
        """Stop file watching."""
        self._stop_watching.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=2.0)

    def add_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add configuration change watcher.

        Args:
            callback: Function called with merged config on changes
        """
        with self._lock:
            self._watchers.append(callback)

    def remove_watcher(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove configuration change watcher.

        Args:
            callback: Watcher function to remove
        """
        with self._lock:
            if callback in self._watchers:
                self._watchers.remove(callback)

    def _notify_watchers(self) -> None:
        """Notify all watchers of configuration change."""
        merged = self.get_all()

        for watcher in self._watchers:
            try:
                watcher(merged)
            except Exception:
                pass  # Ignore watcher errors

    def validate_schema(self, schema: Dict[str, Any]) -> bool:
        """Validate configuration against schema.

        Args:
            schema: Schema dictionary

        Returns:
            True if valid

        Raises:
            ConfigError: If validation fails
        """
        # Simple schema validation
        # In production, use jsonschema or similar
        config = self.get_all()
        return self._validate_dict(config, schema)

    def _validate_dict(self, config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate dictionary against schema.

        Args:
            config: Configuration to validate
            schema: Schema definition

        Returns:
            True if valid

        Raises:
            ConfigError: If validation fails
        """
        for key, expected_type in schema.items():
            if key not in config:
                continue  # Optional fields

            value = config[key]

            if isinstance(expected_type, dict):
                if not isinstance(value, dict):
                    raise ConfigError(f"Expected dict for {key}, got {type(value).__name__}")
                self._validate_dict(value, expected_type)
            elif isinstance(expected_type, type):
                if not isinstance(value, expected_type):
                    raise ConfigError(
                        f"Expected {expected_type.__name__} for {key}, "
                        f"got {type(value).__name__}"
                    )

        return True

    def clear(self, source: Optional[ConfigSource] = None) -> None:
        """Clear configuration.

        Args:
            source: Specific source to clear, or None for all except defaults
        """
        with self._lock:
            if source:
                if source in self._config and source != ConfigSource.COMPILED_DEFAULTS:
                    del self._config[source]
            else:
                # Clear all except defaults
                sources_to_clear = [
                    s for s in self._config.keys()
                    if s != ConfigSource.COMPILED_DEFAULTS
                ]
                for s in sources_to_clear:
                    del self._config[s]

    def __del__(self):
        """Cleanup on deletion."""
        self.stop_watching()


# Global config manager instance
_global_config: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """Get or create global configuration manager.

    Args:
        config_file: Optional config file to load

    Returns:
        Global configuration manager
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager(config_file)
    return _global_config


def set_global_config(config: ConfigManager) -> None:
    """Set the global configuration manager.

    Args:
        config: Configuration manager to use globally
    """
    global _global_config
    _global_config = config