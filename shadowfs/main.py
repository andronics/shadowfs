#!/usr/bin/env python3
"""Main entry point for ShadowFS filesystem.

This module handles:
- Component initialization (ConfigManager, RuleEngine, etc.)
- FUSE filesystem mounting
- Signal handling for graceful shutdown
- Daemon mode support
- Cleanup on exit

Example:
    >>> from shadowfs.main import run_shadowfs
    >>> run_shadowfs(args, config, logger)
"""

import argparse
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

from fuse import FUSE

from shadowfs.core.cache import CacheConfig, CacheManager
from shadowfs.core.config import ConfigManager
from shadowfs.core.logging import Logger
from shadowfs.fuse.operations import ShadowFSOperations
from shadowfs.layers.manager import LayerManager
from shadowfs.rules.engine import Rule, RuleAction, RuleEngine
from shadowfs.transforms.pipeline import TransformPipeline


class ShadowFSMain:
    """
    Main class for ShadowFS filesystem management.

    Handles component lifecycle, FUSE mounting, and shutdown.
    """

    def __init__(self, args: argparse.Namespace, config: Dict, logger: Logger):
        """
        Initialize ShadowFS main controller.

        Args:
            args: Parsed command-line arguments
            config: Configuration dictionary
            logger: Logger instance
        """
        self.args = args
        self.config_dict = config
        self.logger = logger
        self.fuse = None
        self.shutdown_event = threading.Event()

        # Components
        self.config_manager: Optional[ConfigManager] = None
        self.cache_manager: Optional[CacheManager] = None
        self.rule_engine: Optional[RuleEngine] = None
        self.transform_pipeline: Optional[TransformPipeline] = None
        self.layer_manager: Optional[LayerManager] = None
        self.fuse_ops: Optional[ShadowFSOperations] = None

    def initialize_components(self) -> None:
        """
        Initialize all ShadowFS components.

        Creates and configures:
        - ConfigManager
        - CacheManager
        - RuleEngine
        - TransformPipeline
        - LayerManager
        - ShadowFSOperations

        Raises:
            Exception: If component initialization fails
        """
        self.logger.info("Initializing components...")

        # 1. Configuration Manager
        self.logger.debug("Creating ConfigManager")
        self.config_manager = ConfigManager()
        self.config_manager._config = self.config_dict

        # 2. Cache Manager
        self.logger.debug("Creating CacheManager")
        cache_config = self.config_dict.get("cache", {})
        max_size_mb = cache_config.get("max_size_mb", 512)
        ttl_seconds = cache_config.get("ttl_seconds", 300)

        # Create cache configurations for each level
        from shadowfs.core.cache import CacheLevel

        cache_configs = {
            CacheLevel.L1: CacheConfig(
                max_entries=10000,
                max_size_bytes=max_size_mb * 1024 * 1024 // 2,  # Half for L1
                ttl_seconds=ttl_seconds,
                enabled=cache_config.get("enabled", True),
            ),
            CacheLevel.L2: CacheConfig(
                max_entries=5000,
                max_size_bytes=max_size_mb * 1024 * 1024,  # Full size for L2
                ttl_seconds=ttl_seconds * 2,
                enabled=cache_config.get("enabled", True),
            ),
            CacheLevel.L3: CacheConfig(
                max_entries=1000,
                max_size_bytes=max_size_mb * 1024 * 1024 * 2,  # Double for L3
                ttl_seconds=ttl_seconds * 3,
                enabled=cache_config.get("enabled", True),
            ),
        }

        self.cache_manager = CacheManager(configs=cache_configs)

        # 3. Rule Engine
        self.logger.debug("Creating RuleEngine")
        self.rule_engine = RuleEngine()

        # Load rules from configuration
        rules_config = self.config_dict.get("rules", [])
        for rule_dict in rules_config:
            try:
                # Convert rule dict to Rule object
                rule = self._create_rule_from_dict(rule_dict)
                self.rule_engine.add_rule(rule)
                self.logger.debug(f"Added rule: {rule.name}")
            except Exception as e:
                self.logger.warning(f"Failed to load rule: {e}")

        # 4. Transform Pipeline
        self.logger.debug("Creating TransformPipeline")
        self.transform_pipeline = TransformPipeline()

        # Load transforms from configuration
        transforms_config = self.config_dict.get("transforms", [])
        for transform_dict in transforms_config:
            try:
                # Transform loading would happen here
                # For now, just log
                self.logger.debug(f"Transform config: {transform_dict.get('name')}")
            except Exception as e:
                self.logger.warning(f"Failed to load transform: {e}")

        # 5. Virtual Layer Manager
        self.logger.debug("Creating LayerManager")
        sources = [
            source["path"] for source in self.config_dict.get("sources", []) if "path" in source
        ]
        self.layer_manager = LayerManager(sources=sources)

        # Load virtual layers from configuration
        layers_config = self.config_dict.get("virtual_layers", [])
        for layer_dict in layers_config:
            try:
                # Virtual layer loading would happen here
                # For now, just log
                self.logger.debug(f"Virtual layer config: {layer_dict.get('name')}")
            except Exception as e:
                self.logger.warning(f"Failed to load virtual layer: {e}")

        # 6. FUSE Operations
        self.logger.debug("Creating ShadowFSOperations")
        self.fuse_ops = ShadowFSOperations(
            config=self.config_manager,
            layer_manager=self.layer_manager,
            rule_engine=self.rule_engine,
            transform_pipeline=self.transform_pipeline,
            cache=self.cache_manager,
        )

        self.logger.info("All components initialized successfully")

    def _create_rule_from_dict(self, rule_dict: Dict) -> Rule:
        """
        Create Rule object from configuration dictionary.

        Args:
            rule_dict: Rule configuration dictionary

        Returns:
            Rule instance

        Raises:
            ValueError: If rule configuration is invalid
        """
        # Determine action
        rule_type = rule_dict.get("type", "").lower()
        if rule_type == "exclude":
            action = RuleAction.EXCLUDE
        elif rule_type == "include":
            action = RuleAction.INCLUDE
        else:
            raise ValueError(f"Unknown rule type: {rule_type}")

        # Get patterns
        pattern = rule_dict.get("pattern")
        patterns = rule_dict.get("patterns", [])

        if pattern:
            patterns = [pattern]
        elif not patterns:
            raise ValueError("Rule must have 'pattern' or 'patterns'")

        # Create rule
        return Rule(
            name=rule_dict.get("name", "Unnamed Rule"),
            action=action,
            patterns=patterns,
            priority=rule_dict.get("priority", 100),
        )

    def setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Handles:
        - SIGTERM: Graceful shutdown
        - SIGINT: Graceful shutdown (Ctrl+C)
        - SIGHUP: Reload configuration (future)
        """

        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            sig_name = signal.Signals(signum).name
            self.logger.info(f"Received signal {sig_name}, shutting down...")
            self.shutdown_event.set()

            # Unmount filesystem
            if self.fuse:
                self.logger.info("Unmounting filesystem...")
                # FUSE will handle the unmount

        # Register handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        self.logger.debug("Signal handlers registered")

    def mount_filesystem(self) -> int:
        """
        Mount the FUSE filesystem.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        mount_point = self.args.mount

        self.logger.info(f"Mounting ShadowFS at: {mount_point}")

        # Log configuration
        self.logger.info(f"Read-only mode: {self.config_dict.get('readonly', True)}")
        self.logger.info(f"Source directories: {len(self.config_dict.get('sources', []))}")

        # Build FUSE options
        fuse_options = self._build_fuse_options()

        try:
            # Mount filesystem
            self.logger.info("Starting FUSE...")

            # Run FUSE (blocks until unmount)
            FUSE(
                self.fuse_ops,
                mount_point,
                foreground=self.args.foreground,
                **fuse_options,
            )

            self.logger.info("FUSE unmounted successfully")
            return 0

        except RuntimeError as e:
            self.logger.error(f"FUSE mount failed: {e}")
            return 1

        except Exception as e:
            self.logger.error(f"Unexpected error during mount: {e}")
            import traceback

            traceback.print_exc()
            return 1

    def _build_fuse_options(self) -> Dict:
        """
        Build FUSE mount options dictionary.

        Returns:
            Dictionary of FUSE options
        """
        options = {}

        # Read-only mode
        if self.config_dict.get("readonly", True):
            options["ro"] = True

        # Allow other users
        if self.config_dict.get("allow_other", False):
            options["allow_other"] = True

        # No empty files
        options["noempty"] = False

        # Additional FUSE options from command line
        if hasattr(self.args, "fuse_options") and self.args.fuse_options:
            for opt in self.args.fuse_options:
                if "=" in opt:
                    key, value = opt.split("=", 1)
                    options[key] = value
                else:
                    options[opt] = True

        return options

    def cleanup(self) -> None:
        """
        Cleanup resources on shutdown.

        Performs:
        - Cache flush
        - Component cleanup
        - Log final statistics
        """
        self.logger.info("Cleaning up...")

        if self.fuse_ops:
            # Log statistics
            try:
                stats = self.fuse_ops.get_stats()
                self.logger.info(f"Final statistics: {stats}")
            except Exception as e:
                self.logger.warning(f"Failed to get final statistics: {e}")

        if self.cache_manager:
            # Clear cache
            try:
                self.cache_manager.clear()
                self.logger.debug("Cache cleared")
            except Exception as e:
                self.logger.warning(f"Failed to clear cache: {e}")

        self.logger.info("Cleanup complete")

    def run(self) -> int:
        """
        Run ShadowFS main loop.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            # Initialize components
            self.initialize_components()

            # Setup signal handlers
            self.setup_signal_handlers()

            # Mount filesystem (blocks until unmount)
            return self.mount_filesystem()

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            return 130

        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()
            return 1

        finally:
            # Cleanup
            self.cleanup()


def run_shadowfs(args: argparse.Namespace, config: Dict, logger: Logger) -> int:
    """
    Main entry point for running ShadowFS.

    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary
        logger: Logger instance

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Create main controller
    main = ShadowFSMain(args, config, logger)

    # Run
    return main.run()


def main():
    """
    Entry point when run as standalone script.

    Typically called via cli.py, but can be run directly for testing.
    """
    # Import CLI for argument parsing
    from shadowfs.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
