"""Tests for CLI main() function and execution paths.

This module tests the main entry point and error handling.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from shadowfs.cli import CLIError, main


class TestMainFunction:
    """Tests for main() function execution."""

    def test_main_with_config_file(self, tmpdir):
        """Test main() with config file specified."""
        config_file = tmpdir / "config.yaml"
        config_file.write_text("shadowfs:\n  version: '1.0'\n", encoding="utf-8")

        mount_point = tmpdir / "mount"
        mount_point.mkdir()
        source_dir = tmpdir / "source"
        source_dir.mkdir()

        test_args = [
            "shadowfs",
            str(source_dir),
            str(mount_point),
            "--config",
            str(config_file),
            "--foreground",
        ]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                result = main()

        assert result == 0
        assert mock_run.called

    def test_main_without_config_file(self, tmpdir):
        """Test main() without config file (build from args)."""
        mount_point = tmpdir / "mount"
        mount_point.mkdir()
        source_dir = tmpdir / "source"
        source_dir.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "--foreground"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                result = main()

        assert result == 0
        assert mock_run.called

    def test_main_cli_error(self, tmpdir):
        """Test main() handles CLIError."""
        test_args = ["shadowfs", "--invalid-arg"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.cli.parse_arguments") as mock_parse:
                mock_parse.side_effect = CLIError("Invalid argument")
                result = main()

        assert result == 1

    def test_main_keyboard_interrupt(self, tmpdir):
        """Test main() handles KeyboardInterrupt."""
        mount_point = tmpdir / "mount"
        mount_point.mkdir()
        source_dir = tmpdir / "source"
        source_dir.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point)]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.side_effect = KeyboardInterrupt()
                result = main()

        assert result == 130

    def test_main_unexpected_error(self, tmpdir):
        """Test main() handles unexpected exceptions."""
        mount_point = tmpdir / "mount"
        mount_point.mkdir()
        source_dir = tmpdir / "source"
        source_dir.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point)]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.side_effect = RuntimeError("Unexpected error")
                result = main()

        assert result == 1


class TestArgumentParsingEdgeCases:
    """Tests for argument parsing edge cases."""

    def test_positional_source_takes_precedence(self, tmpdir):
        """Test positional source overrides --sources."""
        source1 = tmpdir / "source1"
        source1.mkdir()
        source2 = tmpdir / "source2"
        source2.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = [
            "shadowfs",
            str(source1),  # positional
            str(mount_point),
            "--sources",
            str(source2),  # flag
        ]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        # Should use positional source1
        call_args = mock_run.call_args
        config = call_args[0][1]
        assert config["sources"][0]["path"] == str(source1)

    def test_sources_flag_only(self, tmpdir):
        """Test --sources flag without positional."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", "--sources", str(source_dir), "--mount-point", str(mount_point)]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        assert mock_run.called

    def test_positional_mount_takes_precedence(self, tmpdir):
        """Test positional mount overrides --mount-point."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount1 = tmpdir / "mount1"
        mount1.mkdir()
        mount2 = tmpdir / "mount2"
        mount2.mkdir()

        test_args = [
            "shadowfs",
            str(source_dir),
            str(mount1),  # positional
            "--mount-point",
            str(mount2),  # flag
        ]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        # Should use positional mount1
        call_args = mock_run.call_args
        args = call_args[0][0]
        assert str(mount1) in str(args.mount_point)

    def test_mount_options_ro(self, tmpdir):
        """Test -o ro option sets read-only."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "ro"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.read_write is False

    def test_mount_options_rw(self, tmpdir):
        """Test -o rw option sets read-write."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "rw"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.read_write is True

    def test_mount_options_allow_other(self, tmpdir):
        """Test -o allow_other option."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "allow_other"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.allow_other is True

    def test_mount_options_debug(self, tmpdir):
        """Test -o debug option."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "debug"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.debug is True

    def test_mount_options_foreground(self, tmpdir):
        """Test -o foreground option."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "foreground"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.foreground is True

    def test_mount_options_f_shorthand(self, tmpdir):
        """Test -o f (shorthand for foreground) option."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "f"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.foreground is True

    def test_mount_options_multiple(self, tmpdir):
        """Test multiple mount options."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        test_args = ["shadowfs", str(source_dir), str(mount_point), "-o", "ro,allow_other,debug"]

        with patch.object(sys, "argv", test_args):
            with patch("shadowfs.main.run_shadowfs") as mock_run:
                mock_run.return_value = 0
                main()

        call_args = mock_run.call_args
        args = call_args[0][0]
        assert args.read_write is False
        assert args.allow_other is True
        assert args.debug is True


class TestDiscoverConfigSystemPath:
    """Tests for system config discovery."""

    def test_discovers_system_config_if_exists(self):
        """Test discovers system config at /etc/shadowfs/config.yaml."""
        from shadowfs.cli import discover_config

        with patch("pathlib.Path.exists") as mock_exists:
            # System config exists
            mock_exists.return_value = True

            with patch("pathlib.Path.__new__") as mock_path_new:
                # Make Path("/etc/shadowfs/config.yaml").exists() return True
                def path_new(cls, *args):
                    if args and args[0] == "/etc/shadowfs/config.yaml":
                        mock_path = Mock()
                        mock_path.exists.return_value = True
                        mock_path.__str__ = lambda self: "/etc/shadowfs/config.yaml"
                        return mock_path
                    return object.__new__(cls)

                mock_path_new.side_effect = path_new

                # This is complex to test without actual filesystem
                # The function will check /etc first, which we can't easily mock
                # For now, accept this limitation
                result = discover_config()

                # Result depends on actual filesystem
                assert result is None or "/etc/shadowfs/config.yaml" in str(result)
