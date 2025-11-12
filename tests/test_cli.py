"""Tests for CLI argument parsing and configuration.

This module tests the command-line interface including:
- Argument parsing
- Configuration file loading
- Validation logic
- FUSE options building
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from shadowfs.cli import (
    CLIError,
    build_config_from_args,
    get_fuse_options,
    load_config_from_file,
    main,
    merge_configs,
    parse_arguments,
    print_banner,
    setup_logging,
    validate_runtime_environment,
)
from shadowfs.core.logging import LogLevel


class TestParseArguments:
    """Test argument parsing."""

    def test_parse_basic_arguments(self, tmp_path):
        """Parses basic required arguments."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

        assert args.sources == [str(source_dir)]
        assert args.mount == str(mount_dir)
        assert not args.foreground
        assert not args.debug

    def test_parse_multiple_sources(self, tmp_path):
        """Parses multiple source directories."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source1 = tmp_path / "source1"
        source1.mkdir()

        source2 = tmp_path / "source2"
        source2.mkdir()

        args = parse_arguments(["--sources", str(source1), str(source2), "--mount", str(mount_dir)])

        assert len(args.sources) == 2
        assert str(source1) in args.sources
        assert str(source2) in args.sources

    def test_parse_with_config_file(self, tmp_path):
        """Parses with configuration file."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        config_file = tmp_path / "config.yaml"
        config_file.write_text("shadowfs:\n  sources:\n    - path: /data\n")

        args = parse_arguments(["--config", str(config_file), "--mount", str(mount_dir)])

        assert args.config == str(config_file)
        assert args.mount == str(mount_dir)

    def test_parse_filesystem_options(self, tmp_path):
        """Parses filesystem options."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--read-write",
                "--allow-other",
            ]
        )

        assert args.read_write
        assert args.allow_other

    def test_parse_logging_options(self, tmp_path):
        """Parses logging options."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        log_file = tmp_path / "shadowfs.log"

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--foreground",
                "--debug",
                "--log-file",
                str(log_file),
            ]
        )

        assert args.foreground
        assert args.debug
        assert args.log_file == str(log_file)

    def test_parse_fuse_options(self, tmp_path):
        """Parses FUSE-specific options."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--fuse-opt",
                "direct_io",
                "--fuse-opt",
                "max_read=131072",
            ]
        )

        assert "direct_io" in args.fuse_options
        assert "max_read=131072" in args.fuse_options

    def test_missing_mount_point(self):
        """Raises SystemExit when mount point is missing."""
        with pytest.raises(SystemExit):
            parse_arguments(["--sources", "/data"])

    def test_version_option(self):
        """Displays version and exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_arguments(["--version"])

        assert exc_info.value.code == 0

    def test_help_option(self):
        """Displays help and exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_arguments(["--help"])

        assert exc_info.value.code == 0


class TestValidateArguments:
    """Test argument validation."""

    def test_validates_mount_exists(self, tmp_path):
        """Raises error if mount point doesn't exist."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mount_dir = tmp_path / "nonexistent"

        with pytest.raises(CLIError, match="Mount point does not exist"):
            parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

    def test_validates_mount_is_directory(self, tmp_path):
        """Raises error if mount point is not a directory."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mount_file = tmp_path / "mount.txt"
        mount_file.write_text("not a directory")

        with pytest.raises(CLIError, match="not a directory"):
            parse_arguments(["--sources", str(source_dir), "--mount", str(mount_file)])

    def test_validates_mount_is_empty(self, tmp_path):
        """Raises error if mount point is not empty."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        # Add a file to make it non-empty
        (mount_dir / "file.txt").write_text("content")

        with pytest.raises(CLIError, match="not empty"):
            parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

    def test_validates_source_exists(self, tmp_path):
        """Raises error if source directory doesn't exist."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "nonexistent"

        with pytest.raises(CLIError, match="Source directory does not exist"):
            parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

    def test_validates_source_is_directory(self, tmp_path):
        """Raises error if source is not a directory."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_file = tmp_path / "source.txt"
        source_file.write_text("not a directory")

        with pytest.raises(CLIError, match="Source is not a directory"):
            parse_arguments(["--sources", str(source_file), "--mount", str(mount_dir)])

    def test_validates_config_file_exists(self, tmp_path):
        """Raises error if config file doesn't exist."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(CLIError, match="Configuration file does not exist"):
            parse_arguments(["--config", str(config_file), "--mount", str(mount_dir)])

    def test_requires_config_or_sources(self, tmp_path):
        """Raises error if neither config nor sources specified."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        with pytest.raises(CLIError, match="Either --config or --sources"):
            parse_arguments(["--mount", str(mount_dir)])


class TestLoadConfigFromFile:
    """Test configuration file loading."""

    def test_loads_valid_yaml(self, tmp_path):
        """Loads valid YAML configuration."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "shadowfs": {"sources": [{"path": "/data", "priority": 1}], "readonly": True}
        }

        config_file.write_text(yaml.dump(config_data))

        loaded = load_config_from_file(str(config_file))

        assert "shadowfs" in loaded
        assert loaded["shadowfs"]["readonly"] is True

    def test_raises_on_empty_file(self, tmp_path):
        """Raises error on empty configuration file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        with pytest.raises(CLIError, match="empty"):
            load_config_from_file(str(config_file))

    def test_raises_on_invalid_yaml(self, tmp_path):
        """Raises error on invalid YAML syntax."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: syntax:")

        with pytest.raises(CLIError, match="Failed to parse"):
            load_config_from_file(str(config_file))

    def test_raises_on_non_dict(self, tmp_path):
        """Raises error if YAML is not a dictionary."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- list\n- not\n- dict\n")

        with pytest.raises(CLIError, match="must contain a YAML dictionary"):
            load_config_from_file(str(config_file))

    def test_raises_on_io_error(self):
        """Raises error on I/O failure."""
        with pytest.raises(CLIError, match="Failed to read"):
            load_config_from_file("/nonexistent/config.yaml")


class TestBuildConfigFromArgs:
    """Test configuration building from arguments."""

    def test_builds_basic_config(self, tmp_path):
        """Builds configuration from basic arguments."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

        config = build_config_from_args(args)

        assert config["readonly"] is True
        assert len(config["sources"]) == 1
        assert config["sources"][0]["path"] == str(source_dir.absolute())
        assert config["sources"][0]["priority"] == 1

    def test_builds_with_multiple_sources(self, tmp_path):
        """Builds configuration with multiple sources."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source1 = tmp_path / "source1"
        source1.mkdir()

        source2 = tmp_path / "source2"
        source2.mkdir()

        args = parse_arguments(["--sources", str(source1), str(source2), "--mount", str(mount_dir)])

        config = build_config_from_args(args)

        assert len(config["sources"]) == 2
        assert config["sources"][0]["priority"] == 1
        assert config["sources"][1]["priority"] == 2

    def test_builds_with_read_write(self, tmp_path):
        """Builds configuration with read-write mode."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            ["--sources", str(source_dir), "--mount", str(mount_dir), "--read-write"]
        )

        config = build_config_from_args(args)

        assert config["readonly"] is False

    def test_builds_logging_config(self, tmp_path):
        """Builds logging configuration."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        log_file = tmp_path / "shadowfs.log"

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--debug",
                "--log-file",
                str(log_file),
            ]
        )

        config = build_config_from_args(args)

        assert config["logging"]["level"] == "DEBUG"
        assert config["logging"]["file"] == str(log_file)


class TestMergeConfigs:
    """Test configuration merging."""

    def test_merges_simple_values(self):
        """Merges simple configuration values."""
        file_config = {"readonly": True, "allow_other": False}
        args_config = {"readonly": False}

        merged = merge_configs(file_config, args_config)

        assert merged["readonly"] is False
        assert merged["allow_other"] is False

    def test_merges_nested_dicts(self):
        """Merges nested dictionaries."""
        file_config = {"logging": {"level": "INFO", "file": "/var/log/shadowfs.log"}}

        args_config = {"logging": {"level": "DEBUG"}}

        merged = merge_configs(file_config, args_config)

        assert merged["logging"]["level"] == "DEBUG"
        assert merged["logging"]["file"] == "/var/log/shadowfs.log"

    def test_args_override_file(self):
        """Command-line arguments override file configuration."""
        file_config = {"sources": [{"path": "/data"}], "readonly": True}

        args_config = {"sources": [{"path": "/home/user/data"}], "readonly": False}

        merged = merge_configs(file_config, args_config)

        assert merged["readonly"] is False
        assert merged["sources"] == [{"path": "/home/user/data"}]


class TestGetFuseOptions:
    """Test FUSE options building."""

    def test_builds_foreground_option(self, tmp_path):
        """Builds foreground FUSE option."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            ["--sources", str(source_dir), "--mount", str(mount_dir), "--foreground"]
        )

        options = get_fuse_options(args)

        assert "foreground" in options

    def test_builds_allow_other_option(self, tmp_path):
        """Builds allow_other FUSE option."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            ["--sources", str(source_dir), "--mount", str(mount_dir), "--allow-other"]
        )

        options = get_fuse_options(args)

        assert "allow_other" in options

    def test_builds_readonly_option(self, tmp_path):
        """Builds read-only FUSE option."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

        options = get_fuse_options(args)

        assert "ro" in options

    def test_builds_custom_fuse_options(self, tmp_path):
        """Builds custom FUSE options."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--fuse-opt",
                "direct_io",
                "--fuse-opt",
                "max_read=131072",
            ]
        )

        options = get_fuse_options(args)

        assert "direct_io" in options
        assert "max_read=131072" in options


class TestValidateRuntimeEnvironment:
    """Test runtime environment validation."""

    def test_validates_fuse_availability(self):
        """Validates FUSE library is available."""
        # This test assumes fusepy is installed
        # Should not raise exception
        validate_runtime_environment()

    def test_raises_on_missing_fuse(self):
        """Raises error if FUSE library is missing."""
        with patch.dict(sys.modules, {"fuse": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module named 'fuse'")):
                with pytest.raises(CLIError, match="FUSE library not found"):
                    validate_runtime_environment()

    def test_raises_on_missing_dev_fuse(self):
        """Raises error if /dev/fuse is missing."""
        with patch("os.path.exists", return_value=False):
            with pytest.raises(CLIError, match="/dev/fuse not found"):
                validate_runtime_environment()

    def test_raises_on_no_permission(self):
        """Raises error if no permission to access /dev/fuse."""
        with patch("os.path.exists", return_value=True):
            with patch("os.access", return_value=False):
                with pytest.raises(CLIError, match="No permission"):
                    validate_runtime_environment()

    def test_raises_on_incompatible_fuse(self):
        """Raises error if FUSE library is incompatible."""
        # Create a mock fuse module without FUSE attribute
        mock_fuse = Mock(spec=[])  # Empty spec means no attributes
        with patch.dict("sys.modules", {"fuse": mock_fuse}):
            with pytest.raises(CLIError, match="too old or incompatible"):
                validate_runtime_environment()


class TestConfigPathValidation:
    """Test configuration path validation."""

    def test_validates_config_path_is_file(self, tmp_path):
        """Raises error if config path exists but is not a file."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        # Create a directory instead of a file
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        with pytest.raises(CLIError, match="Configuration path is not a file"):
            parse_arguments(["--config", str(config_dir), "--mount", str(mount_dir)])


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_with_debug_flag(self, tmp_path):
        """Sets up logging with DEBUG level when debug flag is set."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir), "--debug"])

        config = build_config_from_args(args)
        logger = setup_logging(args, config)

        assert logger.get_level() == LogLevel.DEBUG

    def test_setup_logging_with_log_file_in_daemon_mode(self, tmp_path):
        """Sets up logging with log file in daemon mode."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        log_file = tmp_path / "shadowfs.log"

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--log-file",
                str(log_file),
            ]
        )

        config = build_config_from_args(args)
        logger = setup_logging(args, config)

        # Should log message about file logging in daemon mode
        assert logger is not None

    def test_setup_logging_with_log_file_in_foreground_mode(self, tmp_path):
        """Sets up logging with log file in foreground mode."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        log_file = tmp_path / "shadowfs.log"

        args = parse_arguments(
            [
                "--sources",
                str(source_dir),
                "--mount",
                str(mount_dir),
                "--log-file",
                str(log_file),
                "--foreground",
            ]
        )

        config = build_config_from_args(args)
        logger = setup_logging(args, config)

        # Should not log message in foreground mode
        assert logger is not None

    def test_setup_logging_uses_config_log_level(self, tmp_path):
        """Uses log level from config when debug flag not set."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        args = parse_arguments(["--sources", str(source_dir), "--mount", str(mount_dir)])

        config = build_config_from_args(args)
        config["logging"]["level"] = "WARNING"

        logger = setup_logging(args, config)

        assert logger.get_level() == LogLevel.WARNING


class TestPrintBanner:
    """Test banner printing."""

    def test_print_banner_logs_version_info(self):
        """Prints banner with version information."""
        from shadowfs.core.logging import Logger

        logger = Logger("test", level="INFO")

        # Should not raise exception
        print_banner(logger)


class TestMain:
    """Test main entry point."""

    @patch("shadowfs.fuse.shadowfs_main.run_shadowfs")
    @patch("shadowfs.fuse.cli.parse_arguments")
    @patch("shadowfs.fuse.cli.validate_runtime_environment")
    def test_main_successful_execution(self, mock_validate, mock_parse, mock_run, tmp_path):
        """Runs successfully with valid arguments."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Mock parse_arguments to return valid args
        mock_args = Mock()
        mock_args.sources = [str(source_dir)]
        mock_args.mount = str(mount_dir)
        mock_args.config = None
        mock_args.debug = False
        mock_args.foreground = True
        mock_args.log_file = None
        mock_args.read_write = False
        mock_args.allow_other = False
        mock_args.fuse_options = []

        mock_parse.return_value = mock_args
        mock_run.return_value = 0

        result = main()

        assert result == 0
        mock_validate.assert_called_once()
        mock_run.assert_called_once()

    @patch("shadowfs.fuse.cli.parse_arguments")
    def test_main_handles_cli_error(self, mock_parse):
        """Handles CLIError exception."""
        mock_parse.side_effect = CLIError("Test error")

        result = main()

        assert result == 1

    @patch("shadowfs.fuse.cli.parse_arguments")
    def test_main_handles_keyboard_interrupt(self, mock_parse):
        """Handles KeyboardInterrupt exception."""
        mock_parse.side_effect = KeyboardInterrupt()

        result = main()

        assert result == 130

    @patch("shadowfs.fuse.cli.parse_arguments")
    def test_main_handles_unexpected_exception(self, mock_parse):
        """Handles unexpected exceptions."""
        mock_parse.side_effect = Exception("Unexpected error")

        result = main()

        assert result == 1

    @patch("shadowfs.fuse.shadowfs_main.run_shadowfs")
    @patch("shadowfs.fuse.cli.parse_arguments")
    @patch("shadowfs.fuse.cli.validate_runtime_environment")
    @patch("shadowfs.fuse.cli.load_config_from_file")
    def test_main_with_config_file(
        self, mock_load_config, mock_validate, mock_parse, mock_run, tmp_path
    ):
        """Runs with configuration file."""
        mount_dir = tmp_path / "mount"
        mount_dir.mkdir()

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        config_file = tmp_path / "config.yaml"
        config_file.write_text("shadowfs:\n  sources:\n    - path: /data\n")

        # Mock parse_arguments to return args with config
        mock_args = Mock()
        mock_args.config = str(config_file)
        mock_args.sources = [str(source_dir)]  # Need this for build_config_from_args
        mock_args.mount = str(mount_dir)
        mock_args.debug = False
        mock_args.foreground = True
        mock_args.log_file = None
        mock_args.read_write = False
        mock_args.allow_other = False
        mock_args.fuse_options = []

        mock_parse.return_value = mock_args
        mock_load_config.return_value = {"shadowfs": {"sources": [{"path": "/data"}]}}
        mock_run.return_value = 0

        result = main()

        assert result == 0
        mock_load_config.assert_called_once_with(str(config_file))

    def test_main_module_execution(self):
        """Tests __main__ execution block."""
        import subprocess
        import sys

        # Run the cli module as __main__
        result = subprocess.run(
            [sys.executable, "-m", "shadowfs.fuse.cli", "--version"],
            capture_output=True,
            text=True,
        )

        # Should exit with 0
        assert result.returncode == 0
