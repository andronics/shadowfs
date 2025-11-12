"""Tests for ShadowFS main entry point.

This module tests the main controller including:
- Component initialization
- Signal handling
- FUSE mounting
- Cleanup procedures
"""

import argparse
import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from shadowfs.core.logging import Logger
from shadowfs.main import ShadowFSMain, run_shadowfs


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    mount_dir = tmp_path / "mount"
    mount_dir.mkdir()

    # Create test files
    (source_dir / "test.txt").write_text("test content")

    return {"source": source_dir, "mount": mount_dir}


@pytest.fixture
def mock_args(temp_dirs):
    """Create mock command-line arguments."""
    args = argparse.Namespace()
    args.mount = str(temp_dirs["mount"])
    args.sources = [str(temp_dirs["source"])]
    args.config = None
    args.foreground = True
    args.debug = False
    args.log_file = None
    args.read_write = False
    args.allow_other = False
    args.fuse_options = []
    return args


@pytest.fixture
def basic_config(temp_dirs):
    """Create basic configuration dictionary."""
    return {
        "sources": [{"path": str(temp_dirs["source"]), "priority": 1}],
        "readonly": True,
        "allow_other": False,
        "rules": [],
        "transforms": [],
        "virtual_layers": [],
        "cache": {"max_size_mb": 10, "ttl_seconds": 60, "enabled": True},
        "logging": {"level": "INFO"},
    }


@pytest.fixture
def logger():
    """Create test logger."""
    return Logger("test", level="DEBUG")


class TestShadowFSMainInit:
    """Test ShadowFSMain initialization."""

    def test_init_stores_arguments(self, mock_args, basic_config, logger):
        """Stores arguments and configuration."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        assert main.args == mock_args
        assert main.config_dict == basic_config
        assert main.logger == logger
        assert main.fuse is None
        assert not main.shutdown_event.is_set()

    def test_init_creates_shutdown_event(self, mock_args, basic_config, logger):
        """Creates shutdown event."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        assert isinstance(main.shutdown_event, threading.Event)
        assert not main.shutdown_event.is_set()

    def test_init_sets_components_to_none(self, mock_args, basic_config, logger):
        """Initializes components to None."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        assert main.config_manager is None
        assert main.cache_manager is None
        assert main.rule_engine is None
        assert main.transform_pipeline is None
        assert main.layer_manager is None
        assert main.fuse_ops is None


class TestComponentInitialization:
    """Test component initialization."""

    def test_initialize_components(self, mock_args, basic_config, logger):
        """Initializes all components successfully."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.config_manager is not None
        assert main.cache_manager is not None
        assert main.rule_engine is not None
        assert main.transform_pipeline is not None
        assert main.layer_manager is not None
        assert main.fuse_ops is not None

    def test_initializes_config_manager(self, mock_args, basic_config, logger):
        """Initializes ConfigManager with configuration."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.config_manager._config == basic_config

    def test_initializes_cache_manager(self, mock_args, basic_config, logger):
        """Initializes CacheManager with cache configuration."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        # Verify cache manager exists
        assert main.cache_manager is not None

    def test_initializes_rule_engine(self, mock_args, basic_config, logger):
        """Initializes RuleEngine."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.rule_engine is not None

    def test_loads_rules_from_config(self, mock_args, basic_config, logger):
        """Loads rules from configuration."""
        basic_config["rules"] = [
            {"name": "Test Rule", "type": "exclude", "pattern": "*.pyc", "priority": 100}
        ]

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Verify rule was added
        assert len(main.rule_engine) == 1

    def test_initializes_transform_pipeline(self, mock_args, basic_config, logger):
        """Initializes TransformPipeline."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.transform_pipeline is not None

    def test_initializes_layer_manager(self, mock_args, basic_config, logger):
        """Initializes LayerManager with sources."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.layer_manager is not None
        assert len(main.layer_manager.sources) == 1

    def test_initializes_fuse_operations(self, mock_args, basic_config, logger):
        """Initializes ShadowFS with all components."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.initialize_components()

        assert main.fuse_ops is not None
        assert main.fuse_ops.config == main.config_manager
        assert main.fuse_ops.cache == main.cache_manager


class TestRuleCreation:
    """Test rule creation from configuration."""

    def test_create_exclude_rule(self, mock_args, basic_config, logger):
        """Creates exclude rule from configuration."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        rule_dict = {"name": "Test", "type": "exclude", "pattern": "*.tmp", "priority": 50}

        rule = main._create_rule_from_dict(rule_dict)

        assert rule.name == "Test"
        assert rule.patterns == ["*.tmp"]
        assert rule.priority == 50

    def test_create_include_rule(self, mock_args, basic_config, logger):
        """Creates include rule from configuration."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        rule_dict = {"name": "Test", "type": "include", "pattern": "*.py"}

        rule = main._create_rule_from_dict(rule_dict)

        assert rule.name == "Test"

    def test_create_rule_with_patterns_list(self, mock_args, basic_config, logger):
        """Creates rule with multiple patterns."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        rule_dict = {"name": "Test", "type": "exclude", "patterns": ["*.pyc", "*.pyo"]}

        rule = main._create_rule_from_dict(rule_dict)

        assert len(rule.patterns) == 2
        assert "*.pyc" in rule.patterns

    def test_raises_on_unknown_type(self, mock_args, basic_config, logger):
        """Raises error on unknown rule type."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        rule_dict = {"type": "unknown"}

        with pytest.raises(ValueError, match="Unknown rule type"):
            main._create_rule_from_dict(rule_dict)

    def test_raises_on_missing_pattern(self, mock_args, basic_config, logger):
        """Raises error when no pattern specified."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        rule_dict = {"type": "exclude", "name": "Test"}

        with pytest.raises(ValueError, match="must have"):
            main._create_rule_from_dict(rule_dict)


class TestSignalHandling:
    """Test signal handler setup."""

    def test_setup_signal_handlers(self, mock_args, basic_config, logger):
        """Sets up signal handlers."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        main.setup_signal_handlers()

        # Verify handlers are registered (implementation detail)
        # Just verify no exceptions raised

    def test_signal_handler_sets_shutdown_event(self, mock_args, basic_config, logger):
        """Signal handler sets shutdown event."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.setup_signal_handlers()

        # Simulate signal
        signal_handler = signal.getsignal(signal.SIGTERM)
        signal_handler(signal.SIGTERM, None)

        assert main.shutdown_event.is_set()


class TestFuseOptions:
    """Test FUSE options building."""

    def test_builds_readonly_option(self, mock_args, basic_config, logger):
        """Builds read-only FUSE option."""
        main = ShadowFSMain(mock_args, basic_config, logger)

        options = main._build_fuse_options()

        assert options["ro"] is True

    def test_builds_read_write_option(self, mock_args, basic_config, logger):
        """Builds read-write FUSE option."""
        basic_config["readonly"] = False

        main = ShadowFSMain(mock_args, basic_config, logger)

        options = main._build_fuse_options()

        assert "ro" not in options

    def test_builds_allow_other_option(self, mock_args, basic_config, logger):
        """Builds allow_other FUSE option."""
        basic_config["allow_other"] = True

        main = ShadowFSMain(mock_args, basic_config, logger)

        options = main._build_fuse_options()

        assert options["allow_other"] is True

    def test_builds_custom_fuse_options(self, mock_args, basic_config, logger):
        """Builds custom FUSE options from command line."""
        mock_args.fuse_options = ["direct_io", "max_read=131072"]

        main = ShadowFSMain(mock_args, basic_config, logger)

        options = main._build_fuse_options()

        assert options["direct_io"] is True
        assert options["max_read"] == "131072"


class TestMountFilesystem:
    """Test filesystem mounting."""

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_mounts_filesystem(self, mock_fuse, mock_args, basic_config, logger):
        """Mounts FUSE filesystem."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        result = main.mount_filesystem()

        # Verify FUSE was called
        mock_fuse.assert_called_once()
        assert result == 0

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_passes_operations_to_fuse(self, mock_fuse, mock_args, basic_config, logger):
        """Passes FUSE operations to FUSE constructor."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        main.mount_filesystem()

        # First argument should be fuse_ops
        call_args = mock_fuse.call_args
        assert call_args[0][0] == main.fuse_ops

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_passes_mount_point_to_fuse(self, mock_fuse, mock_args, basic_config, logger):
        """Passes mount point to FUSE constructor."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        main.mount_filesystem()

        # Second argument should be mount point
        call_args = mock_fuse.call_args
        assert call_args[0][1] == mock_args.mount

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_handles_runtime_error(self, mock_fuse, mock_args, basic_config, logger):
        """Handles RuntimeError during mount."""
        mock_fuse.side_effect = RuntimeError("Mount failed")

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        result = main.mount_filesystem()

        assert result == 1


class TestCleanup:
    """Test cleanup procedures."""

    def test_cleanup_gets_statistics(self, mock_args, basic_config, logger):
        """Gets final statistics during cleanup."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Mock get_stats
        main.fuse_ops.get_stats = Mock(return_value={"open_files": 0})

        main.cleanup()

        # Verify stats were retrieved
        main.fuse_ops.get_stats.assert_called_once()

    def test_cleanup_clears_cache(self, mock_args, basic_config, logger):
        """Clears cache during cleanup."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Mock cache clear
        main.cache_manager.clear = Mock()

        main.cleanup()

        # Verify cache was cleared
        main.cache_manager.clear.assert_called_once()

    def test_cleanup_handles_exceptions(self, mock_args, basic_config, logger):
        """Handles exceptions during cleanup."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Mock to raise exception
        main.fuse_ops.get_stats = Mock(side_effect=Exception("Stats error"))

        # Should not raise exception
        main.cleanup()


class TestRunShadowFS:
    """Test run_shadowfs entry point."""

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_runs_successfully(self, mock_fuse, mock_args, basic_config, logger):
        """Runs ShadowFS successfully."""
        result = run_shadowfs(mock_args, basic_config, logger)

        # Should return 0 on success
        assert result == 0

    def test_handles_keyboard_interrupt(self, mock_args, basic_config, logger):
        """Handles KeyboardInterrupt gracefully."""
        with patch.object(ShadowFSMain, "initialize_components", side_effect=KeyboardInterrupt()):
            result = run_shadowfs(mock_args, basic_config, logger)

            assert result == 130

    def test_handles_unexpected_exception(self, mock_args, basic_config, logger):
        """Handles unexpected exceptions."""
        with patch.object(
            ShadowFSMain, "initialize_components", side_effect=Exception("Test error")
        ):
            result = run_shadowfs(mock_args, basic_config, logger)

            assert result == 1

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_cleanup_called_on_success(self, mock_fuse, mock_args, basic_config, logger):
        """Cleanup is called even on success."""
        with patch.object(ShadowFSMain, "cleanup") as mock_cleanup:
            run_shadowfs(mock_args, basic_config, logger)

            mock_cleanup.assert_called_once()

    def test_cleanup_called_on_exception(self, mock_args, basic_config, logger):
        """Cleanup is called even on exception."""
        with patch.object(
            ShadowFSMain, "initialize_components", side_effect=Exception("Test error")
        ):
            with patch.object(ShadowFSMain, "cleanup") as mock_cleanup:
                run_shadowfs(mock_args, basic_config, logger)

                mock_cleanup.assert_called_once()


class TestExceptionHandling:
    """Test exception handling during initialization."""

    def test_handles_rule_loading_exception(self, mock_args, basic_config, logger):
        """Handles exception when loading invalid rule."""
        # Add invalid rule config
        basic_config["rules"] = [{"name": "Invalid", "type": "unknown"}]

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Should not raise exception, but log warning
        assert main.rule_engine is not None

    def test_handles_transform_loading_exception(self, mock_args, basic_config, logger):
        """Handles exception when loading transform."""
        # Add transform config (currently just logs)
        basic_config["transforms"] = [{"name": "Test Transform"}]

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Should not raise exception
        assert main.transform_pipeline is not None

    def test_handles_virtual_layer_loading_exception(self, mock_args, basic_config, logger):
        """Handles exception when loading virtual layer."""
        # Add virtual layer config (currently just logs)
        basic_config["virtual_layers"] = [{"name": "Test Layer"}]

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Should not raise exception
        assert main.layer_manager is not None

    def test_cleanup_handles_cache_clear_exception(self, mock_args, basic_config, logger):
        """Handles exception when clearing cache during cleanup."""
        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        # Mock cache.clear() to raise exception
        main.cache_manager.clear = Mock(side_effect=Exception("Clear failed"))

        # Should not raise exception
        main.cleanup()

    @patch("shadowfs.fuse.shadowfs_main.FUSE")
    def test_mount_handles_unexpected_exception(self, mock_fuse, mock_args, basic_config, logger):
        """Handles unexpected exception during mount."""
        # Make FUSE raise unexpected exception (not RuntimeError)
        mock_fuse.side_effect = ValueError("Unexpected error")

        main = ShadowFSMain(mock_args, basic_config, logger)
        main.initialize_components()

        result = main.mount_filesystem()

        assert result == 1


class TestMainEntryPoints:
    """Test main entry points."""

    @patch("shadowfs.fuse.cli.main")
    def test_main_calls_cli_main(self, mock_cli_main):
        """Tests main() calls cli_main."""
        from shadowfs.main import main

        mock_cli_main.return_value = 0

        result = main()

        assert result == 0
        mock_cli_main.assert_called_once()

    def test_main_module_execution(self):
        """Tests __main__ execution block."""
        import subprocess
        import sys

        # Run the module as __main__
        result = subprocess.run(
            [sys.executable, "-m", "shadowfs.fuse.shadowfs_main", "--version"],
            capture_output=True,
            text=True,
        )

        # Should exit with 0 (version argument handled by cli)
        assert result.returncode == 0
