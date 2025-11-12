"""ShadowFS Core - Shared utilities and infrastructure.

This module combines functionality from the former foundation and infrastructure layers,
providing core utilities used throughout the ShadowFS codebase.

Import specific functions from submodules:
    from shadowfs.core.cache import CacheManager
    from shadowfs.core.config import ConfigManager
    from shadowfs.core import constants
    from shadowfs.core import file_ops
    from shadowfs.core import logging
    from shadowfs.core import metrics
    from shadowfs.core import path_utils
    from shadowfs.core import validators
"""

# Re-export main module references for convenience
from shadowfs.core import (
    cache,
    config,
    constants,
    file_ops,
    logging,
    metrics,
    path_utils,
    validators,
)

__all__ = [
    "cache",
    "config",
    "constants",
    "file_ops",
    "logging",
    "metrics",
    "path_utils",
    "validators",
]
