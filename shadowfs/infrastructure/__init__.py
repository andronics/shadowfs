"""ShadowFS Infrastructure Layer (Layer 2).

This layer provides core services used by higher layers:
- ConfigManager: Hierarchical configuration with hot-reload
- CacheManager: Multi-level LRU cache with TTL
- Logger: Structured logging system
- Metrics: Performance metrics collection (Prometheus format)

These components build on the Foundation Layer (Layer 1) and enable
the Integration Layer (Layer 3) and Application Layer (Layer 4).
"""

from .cache_manager import (
    CacheConfig,
    CacheEntry,
    CacheLevel,
    CacheManager,
    LRUCache,
    get_cache_manager,
    set_global_cache,
)
from .config_manager import ConfigError
from .config_manager import ConfigManager as Config
from .config_manager import ConfigSource, ConfigValue, get_config_manager, set_global_config
from .logger import Logger, LogLevel, LogRecord, get_logger, set_global_logger
from .metrics import (
    Metric,
    MetricsCollector,
    MetricType,
    MetricValue,
    get_metrics,
    set_global_metrics,
)

__all__ = [
    # Logger exports
    "Logger",
    "LogLevel",
    "LogRecord",
    "get_logger",
    "set_global_logger",
    # Metrics exports
    "MetricType",
    "MetricValue",
    "Metric",
    "MetricsCollector",
    "get_metrics",
    "set_global_metrics",
    # CacheManager exports
    "CacheLevel",
    "CacheEntry",
    "CacheConfig",
    "LRUCache",
    "CacheManager",
    "get_cache_manager",
    "set_global_cache",
    # ConfigManager exports
    "ConfigSource",
    "ConfigValue",
    "ConfigError",
    "Config",
    "get_config_manager",
    "set_global_config",
]
