#!/usr/bin/env python3
"""Command-line interface for ShadowFS.

This module provides the CLI for mounting and managing ShadowFS filesystems:
- Argument parsing and validation
- Configuration file loading
- Mount point validation
- FUSE options configuration
- Help and version information

Example:
    >>> from shadowfs.cli import parse_arguments
    >>> args = parse_arguments(['--sources', '/data', '--mount', '/mnt/shadowfs'])
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from shadowfs.core.logging import Logger

# Version information
VERSION = "1.0.0"
DESCRIPTION = "ShadowFS - Dynamic Filesystem Transformation Layer"


class CLIError(Exception):
    """Exception raised for CLI-related errors."""

    pass


def parse_mount_options(options_str: str) -> Dict[str, any]:
    """
    Parse comma-delimited mount options into a dictionary.

    Supports both boolean flags and key=value pairs. Values are automatically
    converted to appropriate types (int, float, bool, or str).

    Args:
        options_str: Comma-delimited options string (e.g., "ro,allow_other,max_size=512")

    Returns:
        Dictionary of parsed options

    Examples:
        >>> parse_mount_options("ro,allow_other")
        {'ro': True, 'allow_other': True}

        >>> parse_mount_options("max_size=512,debug")
        {'max_size': 512, 'debug': True}

        >>> parse_mount_options("threshold=0.75,enabled=true")
        {'threshold': 0.75, 'enabled': True}
    """
    options = {}
    if not options_str:
        return options

    for opt in options_str.split(','):
        opt = opt.strip()
        if not opt:
            continue

        if '=' in opt:
            key, value = opt.split('=', 1)
            key = key.strip()
            value = value.strip()

            # Try to parse value as int
            try:
                options[key] = int(value)
                continue
            except ValueError:
                pass

            # Try to parse value as float
            try:
                options[key] = float(value)
                continue
            except ValueError:
                pass

            # Parse boolean strings
            if value.lower() in ('true', 'yes', '1', 'on'):
                options[key] = True
            elif value.lower() in ('false', 'no', '0', 'off'):
                options[key] = False
            else:
                # Keep as string
                options[key] = value
        else:
            # Boolean flag (presence means True)
            options[opt] = True

    return options


def discover_config() -> Optional[str]:
    """
    Auto-discover configuration file following XDG Base Directory Specification.

    Search order:
    1. /etc/shadowfs/config.yaml (system-wide configuration)
    2. ~/.config/shadowfs/config.yaml (user-specific configuration)
    3. None (use compiled defaults)

    The XDG_CONFIG_HOME environment variable is respected for user config location.

    Returns:
        Path to configuration file if found, None otherwise

    Examples:
        >>> config_file = discover_config()
        >>> if config_file:
        ...     print(f"Found config at: {config_file}")
    """
    # System-wide configuration
    system_config = Path("/etc/shadowfs/config.yaml")
    if system_config.exists():
        return str(system_config)

    # User-specific configuration (respect XDG_CONFIG_HOME)
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        user_config = Path(xdg_config_home) / "shadowfs" / "config.yaml"
    else:
        user_config = Path.home() / ".config" / "shadowfs" / "config.yaml"

    if user_config.exists():
        return str(user_config)

    return None


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Argument list to parse (defaults to sys.argv[1:])

    Returns:
        Parsed arguments namespace

    Raises:
        SystemExit: On invalid arguments or --help/--version
    """
    parser = argparse.ArgumentParser(
        prog="shadowfs",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple mount (new syntax)
  shadowfs /data /mnt/shadowfs

  # With mount options (new syntax)
  shadowfs /data /mnt/shadowfs -o ro,allow_other,debug

  # With configuration file
  shadowfs /data /mnt/shadowfs -c shadowfs.yaml

  # Foreground mode for debugging
  shadowfs /data /mnt/shadowfs -f -o debug

  # Complex options
  shadowfs /data /mnt/shadowfs -o allow_other,max_size=512,debug

  # Legacy syntax (still supported)
  shadowfs --sources /data --mount /mnt/shadowfs --allow-other

For more information, see: https://github.com/andronics/shadowfs
        """,
    )

    # Version
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    # Positional arguments (new style)
    parser.add_argument(
        "source",
        nargs="?",
        help="Source directory to expose (positional, or use --sources)",
    )

    parser.add_argument(
        "mount",
        nargs="?",
        help="Mount point directory (positional, or use --mount)",
    )

    # Configuration file
    parser.add_argument(
        "-c",
        "--config",
        metavar="FILE",
        type=str,
        help="Configuration file path (auto-discovered if not specified)",
    )

    # Mount options (new style)
    parser.add_argument(
        "-o",
        "--options",
        metavar="OPTIONS",
        type=str,
        help="Mount options (comma-delimited, e.g., 'ro,allow_other,debug')",
    )

    # Legacy arguments (for backward compatibility)
    legacy_group = parser.add_argument_group("legacy options (deprecated, use positional args)")

    # Source directories (legacy)
    legacy_group.add_argument(
        "-s",
        "--sources",
        metavar="DIR",
        nargs="+",
        type=str,
        help="Source directories to expose (use positional 'source' instead)",
    )

    # Mount point (legacy)
    legacy_group.add_argument(
        "-m",
        "--mount-point",
        metavar="DIR",
        type=str,
        dest="mount_flag",
        help="Mount point directory (use positional 'mount' instead)",
    )

    # Filesystem options
    fs_group = parser.add_argument_group("filesystem options")

    fs_group.add_argument(
        "--read-write",
        action="store_true",
        help="Mount in read-write mode (default: read-only)",
    )

    fs_group.add_argument(
        "--allow-other",
        action="store_true",
        help="Allow other users to access the filesystem",
    )

    # Logging options
    log_group = parser.add_argument_group("logging options")

    log_group.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )

    log_group.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    log_group.add_argument(
        "--log-file",
        metavar="FILE",
        type=str,
        help="Log file path (default: /var/log/shadowfs/shadowfs.log)",
    )

    # FUSE options
    fuse_group = parser.add_argument_group("FUSE options")

    fuse_group.add_argument(
        "--fuse-opt",
        metavar="OPT",
        action="append",
        dest="fuse_options",
        help="Additional FUSE options (can be specified multiple times)",
    )

    # Parse arguments
    parsed = parser.parse_args(args)

    # Handle positional vs flag arguments (backward compatibility)
    # Priority: positional args > flag args
    if parsed.source and not parsed.sources:
        parsed.sources = [parsed.source]
    elif parsed.sources and not parsed.source:
        parsed.source = parsed.sources[0] if parsed.sources else None
    elif parsed.source and parsed.sources:
        # Both specified - warn but use positional
        print("Warning: Both positional 'source' and --sources specified, using positional", file=sys.stderr)
        parsed.sources = [parsed.source]

    if parsed.mount and not hasattr(parsed, 'mount_flag'):
        # Positional mount is set
        parsed.mount_point = parsed.mount
    elif hasattr(parsed, 'mount_flag') and parsed.mount_flag and not parsed.mount:
        # Legacy --mount-point is set
        parsed.mount_point = parsed.mount_flag
        parsed.mount = parsed.mount_flag
    elif parsed.mount and hasattr(parsed, 'mount_flag') and parsed.mount_flag:
        # Both specified - warn but use positional
        print("Warning: Both positional 'mount' and --mount-point specified, using positional", file=sys.stderr)
        parsed.mount_point = parsed.mount
    else:
        parsed.mount_point = parsed.mount

    # Parse mount options if provided (-o flag)
    if parsed.options:
        mount_opts = parse_mount_options(parsed.options)

        # Apply parsed options to args (they override individual flags)
        for key, value in mount_opts.items():
            # Map common option names to arg attributes
            if key == 'ro' and value:
                parsed.read_write = False
            elif key == 'rw' and value:
                parsed.read_write = True
            elif key == 'allow_other':
                parsed.allow_other = value
            elif key == 'debug':
                parsed.debug = value
            elif key == 'foreground' or key == 'f':
                parsed.foreground = value
            # Store all mount options for later use
            if not hasattr(parsed, 'mount_options'):
                parsed.mount_options = {}
            parsed.mount_options[key] = value

    # Auto-discover config if not specified
    if not parsed.config:
        discovered = discover_config()
        if discovered:
            parsed.config = discovered

    # Validate arguments
    _validate_arguments(parsed)

    return parsed


def _validate_arguments(args: argparse.Namespace) -> None:
    """
    Validate parsed arguments.

    Args:
        args: Parsed arguments namespace

    Raises:
        CLIError: If validation fails
    """
    # Either config or sources must be specified
    if not args.config and not args.sources:
        raise CLIError(
            "Either --config or source directory must be specified\n"
            "Usage: shadowfs /source /mount  or  shadowfs --sources /source --mount /mount\n"
            "Use --help for more information"
        )

    # Validate mount point (use mount_point if set, otherwise mount)
    mount_dir = args.mount_point if hasattr(args, 'mount_point') and args.mount_point else args.mount
    if not mount_dir:
        raise CLIError(
            "Mount point must be specified\n"
            "Usage: shadowfs /source /mount\n"
            "Use --help for more information"
        )

    mount_path = Path(mount_dir)

    # Mount point must exist
    if not mount_path.exists():
        raise CLIError(f"Mount point does not exist: {mount_dir}")

    # Mount point must be a directory
    if not mount_path.is_dir():
        raise CLIError(f"Mount point is not a directory: {mount_dir}")

    # Mount point must be empty (safety check)
    if list(mount_path.iterdir()):
        raise CLIError(
            f"Mount point is not empty: {mount_dir}\n"
            "For safety, ShadowFS requires an empty mount point"
        )

    # Validate source directories (if specified)
    if args.sources:
        for source in args.sources:
            source_path = Path(source)

            if not source_path.exists():
                raise CLIError(f"Source directory does not exist: {source}")

            if not source_path.is_dir():
                raise CLIError(f"Source is not a directory: {source}")

    # Validate config file (if specified)
    if args.config:
        config_path = Path(args.config)

        if not config_path.exists():
            raise CLIError(f"Configuration file does not exist: {args.config}")

        if not config_path.is_file():
            raise CLIError(f"Configuration path is not a file: {args.config}")


def load_config_from_file(config_path: str) -> Dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        CLIError: If file cannot be loaded or parsed
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config:
            raise CLIError(f"Configuration file is empty: {config_path}")

        if not isinstance(config, dict):
            raise CLIError(f"Configuration file must contain a YAML dictionary: {config_path}")

        return config

    except yaml.YAMLError as e:
        raise CLIError(f"Failed to parse configuration file: {config_path}\n{e}")

    except IOError as e:
        raise CLIError(f"Failed to read configuration file: {config_path}\n{e}")


def build_config_from_args(args: argparse.Namespace) -> Dict:
    """
    Build configuration dictionary from command-line arguments.

    Args:
        args: Parsed arguments namespace

    Returns:
        Configuration dictionary for ConfigManager
    """
    config = {
        "readonly": not args.read_write,
        "allow_other": args.allow_other,
    }

    # Add sources
    if args.sources:
        config["sources"] = [
            {"path": os.path.abspath(source), "priority": i + 1}
            for i, source in enumerate(args.sources)
        ]

    # Add logging configuration
    log_level = "DEBUG" if args.debug else "INFO"
    config["logging"] = {"level": log_level}

    if args.log_file:
        config["logging"]["file"] = args.log_file

    return config


def merge_configs(file_config: Dict, args_config: Dict) -> Dict:
    """
    Merge file-based and argument-based configurations.

    Command-line arguments take precedence over file configuration.

    Args:
        file_config: Configuration from file
        args_config: Configuration from command-line arguments

    Returns:
        Merged configuration dictionary
    """
    # Start with file config
    merged = file_config.copy()

    # Override with command-line arguments
    for key, value in args_config.items():
        if value is not None:
            if isinstance(value, dict) and key in merged:
                # Merge nested dictionaries
                merged[key] = {**merged.get(key, {}), **value}
            else:
                # Override scalar values
                merged[key] = value

    return merged


def get_fuse_options(args: argparse.Namespace) -> List[str]:
    """
    Build FUSE mount options from arguments.

    Args:
        args: Parsed arguments namespace

    Returns:
        List of FUSE mount options
    """
    options = []

    # Foreground mode
    if args.foreground:
        options.append("foreground")

    # Allow other users
    if args.allow_other:
        options.append("allow_other")

    # Read-only mode
    if not args.read_write:
        options.append("ro")

    # Additional FUSE options
    if args.fuse_options:
        options.extend(args.fuse_options)

    return options


def setup_logging(args: argparse.Namespace, config: Dict) -> Logger:
    """
    Setup logging based on arguments and configuration.

    Args:
        args: Parsed arguments namespace
        config: Configuration dictionary

    Returns:
        Configured logger instance
    """
    log_level = "DEBUG" if args.debug else config.get("logging", {}).get("level", "INFO")
    log_file = args.log_file or config.get("logging", {}).get("file")

    logger = Logger("shadowfs.cli", level=log_level)

    if log_file and not args.foreground:
        # In daemon mode, log to file
        logger.info(f"Logging to file: {log_file}")

    return logger


def validate_runtime_environment() -> None:
    """
    Validate runtime environment for ShadowFS.

    Checks:
    - FUSE availability
    - Required permissions
    - System requirements

    Raises:
        CLIError: If environment validation fails
    """
    # Check FUSE availability
    try:
        import fuse

        # Check FUSE version
        if not hasattr(fuse, "FUSE"):
            raise CLIError(
                "FUSE library is too old or incompatible\n" "Install fusepy: pip install fusepy"
            )

    except ImportError:
        raise CLIError("FUSE library not found\n" "Install fusepy: pip install fusepy")

    # Check for /dev/fuse
    if not os.path.exists("/dev/fuse"):
        raise CLIError(
            "/dev/fuse not found\n"
            "FUSE kernel module may not be loaded\n"
            "Try: sudo modprobe fuse"
        )

    # Check permissions
    if not os.access("/dev/fuse", os.R_OK | os.W_OK):
        raise CLIError(
            "No permission to access /dev/fuse\n"
            "You may need to:\n"
            "  - Add your user to the 'fuse' group\n"
            "  - Run with sudo (not recommended for production)"
        )


def print_banner(logger: Logger) -> None:
    """
    Print startup banner with version information.

    Args:
        logger: Logger instance
    """
    logger.info("=" * 60)
    logger.info(f"ShadowFS v{VERSION}")
    logger.info(DESCRIPTION)
    logger.info("=" * 60)


def main():
    """
    Main CLI entry point.

    This function is called when the module is run as a script.
    It handles argument parsing, validation, and passes control
    to shadowfs_main.py for filesystem mounting.
    """
    try:
        # Parse arguments
        args = parse_arguments()

        # Validate runtime environment
        validate_runtime_environment()

        # Load configuration
        if args.config:
            file_config = load_config_from_file(args.config)
            args_config = build_config_from_args(args)
            config = merge_configs(file_config, args_config)
        else:
            config = build_config_from_args(args)

        # Setup logging
        logger = setup_logging(args, config)

        # Print banner
        if args.foreground:
            print_banner(logger)

        # Import and run main
        from shadowfs.main import run_shadowfs

        return run_shadowfs(args, config, logger)

    except CLIError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
