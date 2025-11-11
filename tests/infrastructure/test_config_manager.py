#!/usr/bin/env python3
"""Comprehensive tests for the ConfigManager module."""

import os
import time
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from shadowfs.infrastructure.config_manager import (
    ConfigSource,
    ConfigValue,
    ConfigError,
    ConfigManager,
    get_config_manager,
    set_global_config,
)
from shadowfs.foundation.constants import ErrorCode


class TestConfigSource:
    """Tests for ConfigSource enum."""

    def test_config_sources(self):
        """Test all config source values."""
        assert ConfigSource.COMPILED_DEFAULTS.value == 1
        assert ConfigSource.SYSTEM_CONFIG.value == 2
        assert ConfigSource.USER_CONFIG.value == 3
        assert ConfigSource.ENVIRONMENT.value == 4
        assert ConfigSource.CLI_ARGS.value == 5
        assert ConfigSource.RUNTIME.value == 6

    def test_precedence_order(self):
        """Test config source precedence ordering."""
        sources = [
            ConfigSource.COMPILED_DEFAULTS,
            ConfigSource.SYSTEM_CONFIG,
            ConfigSource.USER_CONFIG,
            ConfigSource.ENVIRONMENT,
            ConfigSource.CLI_ARGS,
            ConfigSource.RUNTIME,
        ]

        # Should be in ascending order
        for i in range(len(sources) - 1):
            assert sources[i].value < sources[i + 1].value


class TestConfigValue:
    """Tests for ConfigValue dataclass."""

    def test_config_value_creation(self):
        """Test creating a config value."""
        value = ConfigValue(
            value="test",
            source=ConfigSource.USER_CONFIG,
            validated=True
        )
        assert value.value == "test"
        assert value.source == ConfigSource.USER_CONFIG
        assert value.validated is True
        assert isinstance(value.timestamp, float)

    def test_config_value_defaults(self):
        """Test config value defaults."""
        value = ConfigValue(value=42, source=ConfigSource.RUNTIME)
        assert value.value == 42
        assert value.validated is False
        assert value.timestamp > 0


class TestConfigError:
    """Tests for ConfigError exception."""

    def test_config_error_creation(self):
        """Test creating config error."""
        error = ConfigError("Test error", ErrorCode.INVALID_INPUT)
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.INVALID_INPUT
        assert str(error) == "Test error"

    def test_config_error_default_code(self):
        """Test config error with default error code."""
        error = ConfigError("Test error")
        assert error.error_code == ErrorCode.INVALID_INPUT


class TestConfigManager:
    """Tests for ConfigManager class."""

    @pytest.fixture
    def manager(self):
        """Create test config manager."""
        return ConfigManager()

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
shadowfs:
  cache:
    max_size_mb: 256
    enabled: true
  logging:
    level: DEBUG
    file: /var/log/test.log
""")
            temp_path = f.name

        yield temp_path

        # Cleanup
        try:
            os.unlink(temp_path)
        except:
            pass

    def test_manager_creation(self, manager):
        """Test creating config manager."""
        assert manager is not None
        assert ConfigSource.COMPILED_DEFAULTS in manager._config
        assert isinstance(manager._lock, type(threading.RLock()))

    def test_manager_with_config_file(self, temp_config_file):
        """Test creating manager with config file."""
        manager = ConfigManager(config_file=temp_config_file)
        assert manager.get("shadowfs.cache.max_size_mb") == 256

    def test_default_config(self, manager):
        """Test default configuration values."""
        assert manager.get("shadowfs.cache.enabled") is True
        assert manager.get("shadowfs.cache.max_size_mb") == 512
        assert manager.get("shadowfs.logging.level") == "INFO"

    def test_load_file_success(self, manager, temp_config_file):
        """Test loading configuration from file."""
        manager.load_file(temp_config_file)

        assert manager.get("shadowfs.cache.max_size_mb") == 256
        assert manager.get("shadowfs.logging.level") == "DEBUG"

    def test_load_file_not_found(self, manager):
        """Test loading non-existent file."""
        with pytest.raises(ConfigError) as exc_info:
            manager.load_file("/nonexistent/config.yaml")

        assert "not found" in str(exc_info.value)
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    def test_load_file_invalid_yaml(self, manager):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: {]")
            temp_path = f.name

        try:
            with pytest.raises(ConfigError) as exc_info:
                manager.load_file(temp_path)

            assert "YAML parse error" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_load_file_not_dict(self, manager):
        """Test loading YAML file that's not a dictionary."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("- item1\n- item2\n")
            temp_path = f.name

        try:
            with pytest.raises(ConfigError) as exc_info:
                manager.load_file(temp_path)

            assert "Invalid config format" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_load_dict(self, manager):
        """Test loading configuration from dictionary."""
        config_data = {
            "shadowfs": {
                "cache": {"max_size_mb": 128}
            }
        }

        manager.load_dict(config_data, ConfigSource.RUNTIME)
        assert manager.get("shadowfs.cache.max_size_mb") == 128

    def test_load_environment(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            "SHADOWFS_CACHE_ENABLED": "false",
            "SHADOWFS_LOGGING_LEVEL": "ERROR",
            "SHADOWFS_CUSTOM_VALUE": "1024",
        }):
            # Create manager after setting env vars
            manager = ConfigManager()

            # Environment vars create nested structure
            assert manager.get("shadowfs.cache.enabled") is False
            assert manager.get("shadowfs.logging.level") == "ERROR"
            assert manager.get("shadowfs.custom.value") == 1024

    def test_parse_env_value_bool(self, manager):
        """Test parsing boolean environment values."""
        assert manager._parse_env_value("true") is True
        assert manager._parse_env_value("True") is True
        assert manager._parse_env_value("yes") is True
        assert manager._parse_env_value("1") is True

        assert manager._parse_env_value("false") is False
        assert manager._parse_env_value("False") is False
        assert manager._parse_env_value("no") is False
        assert manager._parse_env_value("0") is False

    def test_parse_env_value_int(self, manager):
        """Test parsing integer environment values."""
        assert manager._parse_env_value("42") == 42
        assert manager._parse_env_value("-10") == -10

    def test_parse_env_value_float(self, manager):
        """Test parsing float environment values."""
        assert manager._parse_env_value("3.14") == 3.14
        assert manager._parse_env_value("-2.5") == -2.5

    def test_parse_env_value_string(self, manager):
        """Test parsing string environment values."""
        assert manager._parse_env_value("hello") == "hello"
        assert manager._parse_env_value("path/to/file") == "path/to/file"

    def test_get_with_default(self, manager):
        """Test getting value with default."""
        assert manager.get("nonexistent.key", default="default_value") == "default_value"
        assert manager.get("shadowfs.cache.max_size_mb", default=0) == 512

    def test_get_nested(self, manager):
        """Test getting nested values."""
        config = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }

        assert manager._get_nested(config, "level1.level2.level3") == "value"
        assert manager._get_nested(config, "level1.level2") == {"level3": "value"}
        assert manager._get_nested(config, "nonexistent") is None
        assert manager._get_nested(config, "level1.nonexistent") is None

    def test_get_nested_non_dict(self, manager):
        """Test getting nested value when intermediate is not dict."""
        config = {
            "key": "string_value"
        }

        assert manager._get_nested(config, "key.nested") is None

    def test_set_simple(self, manager):
        """Test setting simple configuration value."""
        manager.set("test.key", "value")
        assert manager.get("test.key") == "value"

    def test_set_nested(self, manager):
        """Test setting nested configuration value."""
        manager.set("test.level1.level2.key", "value")
        assert manager.get("test.level1.level2.key") == "value"

    def test_set_with_source(self, manager):
        """Test setting value with specific source."""
        manager.set("test.key", "cli_value", source=ConfigSource.CLI_ARGS)
        manager.set("test.key", "runtime_value", source=ConfigSource.RUNTIME)

        # Runtime has higher precedence
        assert manager.get("test.key") == "runtime_value"

    def test_precedence_order(self, manager):
        """Test configuration precedence order."""
        # Set same key in different sources
        manager._config[ConfigSource.COMPILED_DEFAULTS] = {"key": "default"}
        manager._config[ConfigSource.USER_CONFIG] = {"key": "user"}
        manager._config[ConfigSource.ENVIRONMENT] = {"key": "env"}
        manager._config[ConfigSource.RUNTIME] = {"key": "runtime"}

        # Runtime should win
        assert manager.get("key") == "runtime"

        # Remove runtime
        del manager._config[ConfigSource.RUNTIME]
        assert manager.get("key") == "env"

    def test_get_all(self, manager):
        """Test getting merged configuration."""
        manager.load_dict({"custom": {"key": "value"}}, ConfigSource.RUNTIME)

        all_config = manager.get_all()
        assert "shadowfs" in all_config  # From defaults
        assert "custom" in all_config  # From runtime

    def test_deep_merge(self, manager):
        """Test deep merging of configurations."""
        base = {
            "a": {"b": 1, "c": 2},
            "d": 3
        }
        override = {
            "a": {"c": 20, "e": 4},
            "f": 5
        }

        result = manager._deep_merge(base, override)

        assert result["a"]["b"] == 1  # From base
        assert result["a"]["c"] == 20  # Overridden
        assert result["a"]["e"] == 4  # From override
        assert result["d"] == 3  # From base
        assert result["f"] == 5  # From override

    def test_reload(self, manager, temp_config_file):
        """Test reloading configuration."""
        manager.load_file(temp_config_file)
        initial_value = manager.get("shadowfs.cache.max_size_mb")

        # Modify file
        with open(temp_config_file, 'w') as f:
            f.write("""
shadowfs:
  cache:
    max_size_mb: 2048
""")

        manager.reload()
        new_value = manager.get("shadowfs.cache.max_size_mb")

        assert initial_value == 256
        assert new_value == 2048

    def test_watch_file(self, manager, temp_config_file):
        """Test file watching."""
        manager.load_file(temp_config_file)

        changes_detected = []

        def watcher(config):
            changes_detected.append(config)

        manager.add_watcher(watcher)
        manager.watch_file(temp_config_file, interval=0.1)

        # Wait for watch thread to start
        time.sleep(0.2)

        # Modify file
        with open(temp_config_file, 'w') as f:
            f.write("""
shadowfs:
  cache:
    max_size_mb: 4096
""")

        # Wait for change detection
        time.sleep(0.3)

        manager.stop_watching()

        assert len(changes_detected) > 0
        assert changes_detected[-1]["shadowfs"]["cache"]["max_size_mb"] == 4096

    def test_add_remove_watcher(self, manager):
        """Test adding and removing watchers."""
        watcher1 = MagicMock()
        watcher2 = MagicMock()

        manager.add_watcher(watcher1)
        manager.add_watcher(watcher2)

        manager.set("test.key", "value")

        assert watcher1.called
        assert watcher2.called

        watcher1.reset_mock()
        watcher2.reset_mock()

        manager.remove_watcher(watcher1)
        manager.set("test.key2", "value2")

        assert not watcher1.called
        assert watcher2.called

    def test_watcher_exception_handling(self, manager):
        """Test that watcher exceptions don't break notifications."""
        def bad_watcher(config):
            raise Exception("Watcher error")

        good_watcher = MagicMock()

        manager.add_watcher(bad_watcher)
        manager.add_watcher(good_watcher)

        manager.set("test.key", "value")

        # Good watcher should still be called
        assert good_watcher.called

    def test_validate_schema_success(self, manager):
        """Test successful schema validation."""
        manager.load_dict({
            "shadowfs": {
                "cache": {
                    "max_size_mb": 512,
                    "enabled": True
                }
            }
        }, ConfigSource.RUNTIME)

        schema = {
            "shadowfs": {
                "cache": {
                    "max_size_mb": int,
                    "enabled": bool
                }
            }
        }

        assert manager.validate_schema(schema) is True

    def test_validate_schema_type_mismatch(self, manager):
        """Test schema validation with type mismatch."""
        manager.load_dict({
            "shadowfs": {
                "cache": {
                    "max_size_mb": "not_an_int"
                }
            }
        }, ConfigSource.RUNTIME)

        schema = {
            "shadowfs": {
                "cache": {
                    "max_size_mb": int
                }
            }
        }

        with pytest.raises(ConfigError) as exc_info:
            manager.validate_schema(schema)

        assert "Expected int" in str(exc_info.value)

    def test_validate_schema_dict_type_mismatch(self, manager):
        """Test schema validation when dict expected but got other type."""
        manager.load_dict({
            "shadowfs": {
                "cache": "not_a_dict"
            }
        }, ConfigSource.RUNTIME)

        schema = {
            "shadowfs": {
                "cache": {
                    "max_size_mb": int
                }
            }
        }

        with pytest.raises(ConfigError) as exc_info:
            manager.validate_schema(schema)

        assert "Expected dict" in str(exc_info.value)

    def test_clear_specific_source(self, manager):
        """Test clearing specific configuration source."""
        manager.set("test.key", "value", source=ConfigSource.RUNTIME)
        assert manager.get("test.key") == "value"

        manager.clear(source=ConfigSource.RUNTIME)
        assert manager.get("test.key") is None

    def test_clear_all_except_defaults(self, manager):
        """Test clearing all configuration except defaults."""
        manager.set("test.key", "value", source=ConfigSource.USER_CONFIG)
        manager.set("test.key2", "value2", source=ConfigSource.RUNTIME)

        manager.clear()

        assert manager.get("test.key") is None
        assert manager.get("test.key2") is None
        # Defaults should remain
        assert manager.get("shadowfs.cache.enabled") is True

    def test_clear_defaults_protection(self, manager):
        """Test that defaults cannot be cleared with clear()."""
        manager.clear()

        # Defaults should still be there
        assert ConfigSource.COMPILED_DEFAULTS in manager._config

    def test_cleanup_on_deletion(self, manager, temp_config_file):
        """Test cleanup when manager is deleted."""
        manager.watch_file(temp_config_file, interval=0.1)
        time.sleep(0.2)

        assert manager._watch_thread is not None
        assert manager._watch_thread.is_alive()

        del manager
        # Watch thread should stop (daemon thread will be cleaned up)


class TestFileWatching:
    """Tests for file watching functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_watch_nonexistent_file(self, temp_dir):
        """Test watching file that doesn't exist yet."""
        manager = ConfigManager()
        nonexistent = os.path.join(temp_dir, "nonexistent.yaml")

        manager.watch_file(nonexistent, interval=0.1)
        time.sleep(0.2)

        # Should not crash
        manager.stop_watching()

    def test_watch_loop_error_handling(self, temp_dir):
        """Test watch loop handles errors gracefully."""
        manager = ConfigManager()

        # Create and watch file
        config_file = os.path.join(temp_dir, "config.yaml")
        with open(config_file, 'w') as f:
            f.write("shadowfs:\n  test: value\n")

        manager.load_file(config_file)
        manager.watch_file(config_file, interval=0.1)

        time.sleep(0.2)

        # Delete file while watching
        os.unlink(config_file)

        # Should not crash
        time.sleep(0.3)
        manager.stop_watching()

    def test_multiple_watch_files(self, temp_dir):
        """Test watching multiple files."""
        manager = ConfigManager()

        file1 = os.path.join(temp_dir, "config1.yaml")
        file2 = os.path.join(temp_dir, "config2.yaml")

        with open(file1, 'w') as f:
            f.write("shadowfs:\n  key1: value1\n")
        with open(file2, 'w') as f:
            f.write("shadowfs:\n  key2: value2\n")

        manager.load_file(file1)
        manager.load_file(file2)

        manager.watch_file(file1, interval=0.1)
        manager.watch_file(file2, interval=0.1)

        time.sleep(0.2)

        # Modify both files
        with open(file1, 'w') as f:
            f.write("shadowfs:\n  key1: new_value1\n")
        with open(file2, 'w') as f:
            f.write("shadowfs:\n  key2: new_value2\n")

        time.sleep(0.3)

        manager.stop_watching()


class TestGlobalFunctions:
    """Tests for global config manager functions."""

    def test_get_config_manager_creates_instance(self):
        """Test get_config_manager creates new instance."""
        set_global_config(None)
        config = get_config_manager()
        assert config is not None
        assert isinstance(config, ConfigManager)

    def test_get_config_manager_reuses_instance(self):
        """Test get_config_manager reuses existing instance."""
        set_global_config(None)
        config1 = get_config_manager()
        config2 = get_config_manager()
        assert config1 is config2

    def test_set_global_config(self):
        """Test setting global config instance."""
        custom_config = ConfigManager()
        set_global_config(custom_config)

        config = get_config_manager()
        assert config is custom_config

    def test_get_config_manager_with_file(self):
        """Test get_config_manager with config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("shadowfs:\n  test: value\n")
            temp_path = f.name

        try:
            set_global_config(None)
            config = get_config_manager(config_file=temp_path)
            assert config.get("shadowfs.test") == "value"
        finally:
            os.unlink(temp_path)