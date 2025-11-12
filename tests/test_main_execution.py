"""Tests for main execution paths in shadowfs.main.

This module tests the ShadowFSMain class and run_shadowfs function.
"""
import argparse
import signal
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from shadowfs.main import ShadowFSMain, run_shadowfs


class TestShadowFSMainExecution:
    """Tests for ShadowFSMain.run() method."""

    def test_run_success(self, tmpdir):
        """Test successful run."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
            "readonly": True,
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch.object(main, "mount_filesystem") as mock_mount:
            mock_mount.return_value = 0
            result = main.run()

        assert result == 0

    def test_run_keyboard_interrupt(self, tmpdir):
        """Test run() handles KeyboardInterrupt."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch.object(main, "setup_signal_handlers"):
            with patch.object(main, "mount_filesystem") as mock_mount:
                mock_mount.side_effect = KeyboardInterrupt()
                result = main.run()

        assert result == 130

    def test_run_unexpected_error(self, tmpdir):
        """Test run() handles unexpected exceptions."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch.object(main, "setup_signal_handlers"):
            with patch.object(main, "mount_filesystem") as mock_mount:
                mock_mount.side_effect = RuntimeError("Test error")
                result = main.run()

        assert result == 1


class TestMountFilesystem:
    """Tests for mount_filesystem() method."""

    def test_mount_success(self, tmpdir):
        """Test successful filesystem mount."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        args = argparse.Namespace(
            source=str(source_dir),
            sources=[str(source_dir)],
            mount=str(mount_point),
            mount_point=str(mount_point),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(source_dir)}],
            "readonly": True,
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch("shadowfs.main.FUSE") as mock_fuse:
            mock_fuse.return_value = None
            result = main.mount_filesystem()

        assert result == 0
        assert mock_fuse.called

    def test_mount_runtime_error(self, tmpdir):
        """Test mount handles RuntimeError."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        args = argparse.Namespace(
            source=str(source_dir),
            sources=[str(source_dir)],
            mount=str(mount_point),
            mount_point=str(mount_point),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(source_dir)}],
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch("shadowfs.main.FUSE") as mock_fuse:
            mock_fuse.side_effect = RuntimeError("Mount failed")
            result = main.mount_filesystem()

        assert result == 1

    def test_mount_unexpected_error(self, tmpdir):
        """Test mount handles unexpected exceptions."""
        source_dir = tmpdir / "source"
        source_dir.mkdir()
        mount_point = tmpdir / "mount"
        mount_point.mkdir()

        args = argparse.Namespace(
            source=str(source_dir),
            sources=[str(source_dir)],
            mount=str(mount_point),
            mount_point=str(mount_point),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(source_dir)}],
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch("shadowfs.main.FUSE") as mock_fuse:
            mock_fuse.side_effect = ValueError("Unexpected error")
            result = main.mount_filesystem()

        assert result == 1


class TestInitializeComponents:
    """Tests for initialize_components() error handling."""

    def test_transform_load_failure(self, tmpdir):
        """Test initialize_components handles transform load failures."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
            "transforms": [{"name": "test", "type": "template"}],
        }

        logger = Mock()

        # This should not raise an exception
        main = ShadowFSMain(args, config, logger)

        # Just verify initialization completed
        assert main is not None

    def test_virtual_layer_load_failure(self, tmpdir):
        """Test initialize_components handles virtual layer load failures."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
            "virtual_layers": [{"name": "test", "type": "classifier"}],
        }

        logger = Mock()

        # This should not raise an exception
        main = ShadowFSMain(args, config, logger)

        # Just verify initialization completed
        assert main is not None


class TestSignalHandlers:
    """Tests for signal handler setup."""

    def test_setup_signal_handlers(self, tmpdir):
        """Test signal handlers are registered."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
        }

        logger = Mock()

        main = ShadowFSMain(args, config, logger)

        with patch("signal.signal") as mock_signal:
            main.setup_signal_handlers()

        # Check that SIGTERM and SIGINT handlers were registered
        assert mock_signal.call_count == 2


class TestRunShadowFS:
    """Tests for run_shadowfs() function."""

    def test_run_shadowfs(self, tmpdir):
        """Test run_shadowfs function."""
        args = argparse.Namespace(
            source=str(tmpdir / "source"),
            sources=[str(tmpdir / "source")],
            mount=str(tmpdir / "mount"),
            mount_point=str(tmpdir / "mount"),
            config=None,
            foreground=True,
            read_write=False,
            allow_other=False,
            debug=False,
        )

        config = {
            "version": "1.0",
            "sources": [{"path": str(tmpdir / "source")}],
        }

        logger = Mock()

        with patch("shadowfs.main.ShadowFSMain") as mock_main_class:
            mock_main = Mock()
            mock_main.run.return_value = 0
            mock_main_class.return_value = mock_main

            result = run_shadowfs(args, config, logger)

        assert result == 0
        assert mock_main.run.called


class TestMainEntryPoint:
    """Tests for main() entry point."""

    def test_main_entry_point(self):
        """Test main() entry point calls cli_main."""
        from shadowfs.main import main

        with patch("shadowfs.cli.main") as mock_cli_main:
            mock_cli_main.return_value = 0
            result = main()

        assert result == 0
        assert mock_cli_main.called
