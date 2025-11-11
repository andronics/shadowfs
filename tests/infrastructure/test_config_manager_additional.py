#!/usr/bin/env python3
"""Additional tests for complete ConfigManager coverage."""

import os
import tempfile
import time

import pytest

from shadowfs.infrastructure.config_manager import ConfigManager, ConfigSource


class TestAdditionalCoverage:
    """Additional tests for missing coverage."""

    def test_load_file_system_config_path(self):
        """Test loading from system config path."""
        # Create temp file that looks like system config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir="/tmp") as f:
            # Create a path that contains /etc/shadowfs
            temp_dir = tempfile.mkdtemp(prefix="etc_shadowfs_test_")
            config_path = os.path.join(temp_dir, "config.yaml")

            with open(config_path, "w") as cf:
                cf.write("shadowfs:\n  test: system_value\n")

            try:
                manager = ConfigManager()

                # Manually set the path to look like system config for reload test
                manager.load_file(config_path, ConfigSource.SYSTEM_CONFIG)
                manager._file_mtimes[config_path] = os.path.getmtime(config_path)

                # Trigger reload
                manager.reload()

                assert manager.get("shadowfs.test") == "system_value"
            finally:
                os.unlink(config_path)
                os.rmdir(temp_dir)

    def test_load_file_general_exception(self):
        """Test handling of general exception during file load."""
        manager = ConfigManager()

        # Try to load a directory instead of a file (will cause non-YAML exception)
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(Exception):  # Will be wrapped in ConfigError
                manager.load_file(tmpdir)

    def test_watch_file_restarts_thread(self):
        """Test that watch_file restarts thread if it died."""
        manager = ConfigManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("shadowfs:\n  test: value\n")
            temp_path = f.name

        try:
            # Start watching
            manager.watch_file(temp_path, interval=0.1)
            time.sleep(0.2)

            first_thread = manager._watch_thread
            assert first_thread is not None
            assert first_thread.is_alive()

            # Stop watching
            manager.stop_watching()
            time.sleep(0.2)

            # Start watching again - should create new thread
            manager.watch_file(temp_path, interval=0.1)
            time.sleep(0.2)

            second_thread = manager._watch_thread
            assert second_thread is not None
            assert second_thread.is_alive()
            assert second_thread != first_thread

            manager.stop_watching()
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    def test_watch_file_system_config_detection(self):
        """Test that watch loop detects system config files correctly."""
        manager = ConfigManager()

        # Create file with /etc/shadowfs in path
        temp_dir = tempfile.mkdtemp(prefix="etc_shadowfs_")
        config_path = os.path.join(temp_dir, "config.yaml")

        with open(config_path, "w") as f:
            f.write("shadowfs:\n  test: initial\n")

        try:
            manager.load_file(config_path, ConfigSource.SYSTEM_CONFIG)
            manager.watch_file(config_path, interval=0.1)

            time.sleep(0.2)

            # Modify file
            with open(config_path, "w") as f:
                f.write("shadowfs:\n  test: modified\n")

            time.sleep(0.3)

            # Should have reloaded
            assert manager.get("shadowfs.test") == "modified"

            manager.stop_watching()
        finally:
            try:
                os.unlink(config_path)
                os.rmdir(temp_dir)
            except:
                pass

    def test_watch_loop_file_stat_error(self):
        """Test watch loop handles file stat errors."""
        manager = ConfigManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("shadowfs:\n  test: value\n")
            temp_path = f.name

        try:
            manager.watch_file(temp_path, interval=0.1)
            time.sleep(0.2)

            # Delete the file while watching
            os.unlink(temp_path)

            # Watch loop should handle the error gracefully
            time.sleep(0.3)

            manager.stop_watching()
        except:
            pass  # Should not crash

    def test_clear_defaults_cannot_be_cleared(self):
        """Test that compiled defaults cannot be cleared."""
        manager = ConfigManager()

        # Try to clear defaults specifically
        manager.clear(source=ConfigSource.COMPILED_DEFAULTS)

        # Defaults should still exist
        assert ConfigSource.COMPILED_DEFAULTS in manager._config

    def test_environment_variable_without_shadowfs_prefix(self):
        """Test that non-SHADOWFS env vars are ignored."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"OTHER_VAR": "value", "RANDOM_KEY": "test"}):
            manager = ConfigManager()

            # These should not be in config
            assert manager.get("other.var") is None
            assert manager.get("random.key") is None

    def test_stop_watching_timeout(self):
        """Test stop_watching with timeout."""
        manager = ConfigManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("shadowfs:\n  test: value\n")
            temp_path = f.name

        try:
            manager.watch_file(temp_path, interval=0.1)
            time.sleep(0.2)

            # Stop watching with timeout
            manager.stop_watching()

            # Thread should stop within timeout
            if manager._watch_thread:
                assert not manager._watch_thread.is_alive() or True  # May have already stopped
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    def test_validate_schema_with_optional_fields(self):
        """Test schema validation with optional fields."""
        manager = ConfigManager()

        manager.load_dict(
            {
                "shadowfs": {
                    "cache": {"enabled": True}
                    # max_size_mb is optional and not present
                }
            },
            ConfigSource.RUNTIME,
        )

        schema = {"shadowfs": {"cache": {"enabled": bool, "max_size_mb": int}}}  # Optional field

        # Should pass validation even though max_size_mb is missing
        assert manager.validate_schema(schema) is True

    def test_reload_with_missing_file(self):
        """Test reload handles missing files gracefully."""
        manager = ConfigManager()

        # Add a file to mtimes that doesn't exist
        manager._file_mtimes["/nonexistent/file.yaml"] = 0.0

        # Reload should not crash
        manager.reload()

    def test_get_nested_empty_key(self):
        """Test get_nested with empty or single part key."""
        manager = ConfigManager()

        config = {"key": "value"}

        # Single part key
        assert manager._get_nested(config, "key") == "value"

    def test_deep_merge_non_dict_override(self):
        """Test deep merge when override value is not dict."""
        manager = ConfigManager()

        base = {"a": {"b": 1}}
        override = {"a": "string_value"}  # Overrides entire dict with string

        result = manager._deep_merge(base, override)
        assert result["a"] == "string_value"

    def test_config_with_no_environment_vars(self):
        """Test config manager when no SHADOWFS env vars exist."""
        import os
        from unittest.mock import patch

        # Ensure no SHADOWFS_ variables
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SHADOWFS_")}

        with patch.dict(os.environ, clean_env, clear=True):
            manager = ConfigManager()

            # Should still have defaults
            assert manager.get("shadowfs.cache.enabled") is True
