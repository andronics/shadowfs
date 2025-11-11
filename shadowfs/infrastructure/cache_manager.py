#!/usr/bin/env python3
"""Multi-level LRU cache with TTL support for ShadowFS.

This module provides a hierarchical caching system with:
- Multiple cache levels (L1, L2, L3)
- LRU eviction policy
- TTL-based expiration
- Size-based limits
- Thread-safe operations
- Cache statistics
- Selective invalidation
- Hierarchical cache warming

Example:
    >>> cache = CacheManager()
    >>> cache.set("file_attrs", "path/to/file", attrs, level=CacheLevel.L1)
    >>> attrs = cache.get("file_attrs", "path/to/file")
    >>> cache.invalidate_path("path/to/file")
"""

import time
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set
from shadowfs.foundation.constants import ErrorCode


class CacheLevel(Enum):
    """Cache levels with different characteristics."""

    L1 = "l1"  # File attributes (stat results) - small, short TTL
    L2 = "l2"  # File content - medium size, medium TTL
    L3 = "l3"  # Transformed content - large, long TTL


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""

    key: str
    value: Any
    size: int
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)

    def is_expired(self, ttl: float) -> bool:
        """Check if entry has expired.

        Args:
            ttl: Time-to-live in seconds

        Returns:
            True if expired
        """
        return time.time() - self.timestamp > ttl

    def touch(self) -> None:
        """Update access time and count."""
        self.last_access = time.time()
        self.access_count += 1


@dataclass
class CacheConfig:
    """Configuration for a cache level."""

    max_entries: int
    max_size_bytes: int
    ttl_seconds: float
    enabled: bool = True

    def validate(self) -> None:
        """Validate cache configuration."""
        if self.max_entries <= 0:
            raise ValueError(f"max_entries must be positive: {self.max_entries}")
        if self.max_size_bytes <= 0:
            raise ValueError(f"max_size_bytes must be positive: {self.max_size_bytes}")
        if self.ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive: {self.ttl_seconds}")


class LRUCache:
    """Thread-safe LRU cache with TTL and size limits."""

    def __init__(self, config: CacheConfig):
        """Initialize LRU cache.

        Args:
            config: Cache configuration
        """
        self.config = config
        self.config.validate()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._current_size = 0

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.config.enabled:
            self._misses += 1
            return None

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired(self.config.ttl_seconds):
                self._remove_entry(key)
                self._expirations += 1
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, size: int) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            size: Size in bytes
        """
        if not self.config.enabled:
            return

        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)

            # Check if value fits
            if size > self.config.max_size_bytes:
                return  # Too large to cache

            # Evict entries until there's space
            while (len(self._cache) >= self.config.max_entries or
                   self._current_size + size > self.config.max_size_bytes):
                if not self._cache:
                    break  # Nothing to evict
                self._evict_lru()

            # Add new entry
            entry = CacheEntry(key=key, value=value, size=size)
            self._cache[key] = entry
            self._current_size += size

    def invalidate(self, key: str) -> bool:
        """Remove entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was removed
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0

    def _remove_entry(self, key: str) -> None:
        """Remove entry and update size.

        Args:
            key: Cache key
        """
        if key in self._cache:
            entry = self._cache[key]
            self._current_size -= entry.size
            del self._cache[key]

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            # First item is LRU
            key = next(iter(self._cache))
            self._remove_entry(key)
            self._evictions += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0

            return {
                "entries": len(self._cache),
                "size_bytes": self._current_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "expirations": self._expirations,
            }

    def get_entries(self) -> List[Tuple[str, int, float]]:
        """Get all cache entries with metadata.

        Returns:
            List of (key, size, age) tuples
        """
        with self._lock:
            current_time = time.time()
            return [
                (key, entry.size, current_time - entry.timestamp)
                for key, entry in self._cache.items()
            ]


class CacheManager:
    """Multi-level cache manager for ShadowFS."""

    DEFAULT_CONFIGS = {
        CacheLevel.L1: CacheConfig(
            max_entries=10000,
            max_size_bytes=10 * 1024 * 1024,  # 10MB
            ttl_seconds=60.0,
        ),
        CacheLevel.L2: CacheConfig(
            max_entries=1000,
            max_size_bytes=512 * 1024 * 1024,  # 512MB
            ttl_seconds=300.0,
        ),
        CacheLevel.L3: CacheConfig(
            max_entries=100,
            max_size_bytes=1024 * 1024 * 1024,  # 1GB
            ttl_seconds=600.0,
        ),
    }

    def __init__(self, configs: Optional[Dict[CacheLevel, CacheConfig]] = None):
        """Initialize cache manager.

        Args:
            configs: Cache configurations per level (uses defaults if None)
        """
        self.configs = configs or self.DEFAULT_CONFIGS.copy()
        self.caches: Dict[CacheLevel, LRUCache] = {}

        # Initialize caches for each level
        for level, config in self.configs.items():
            self.caches[level] = LRUCache(config)

        # Path-based invalidation tracking
        self._path_keys: Dict[str, Set[Tuple[CacheLevel, str]]] = {}
        self._path_lock = threading.RLock()

    def get(
        self,
        namespace: str,
        key: str,
        level: CacheLevel = CacheLevel.L2
    ) -> Optional[Any]:
        """Get value from cache.

        Args:
            namespace: Cache namespace (e.g., "file_attrs", "content")
            key: Cache key (e.g., file path)
            level: Cache level

        Returns:
            Cached value or None
        """
        cache = self.caches.get(level)
        if not cache:
            return None

        full_key = f"{namespace}:{key}"
        return cache.get(full_key)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        size: Optional[int] = None,
        level: CacheLevel = CacheLevel.L2
    ) -> None:
        """Set value in cache.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            size: Size in bytes (estimated if None)
            level: Cache level
        """
        cache = self.caches.get(level)
        if not cache:
            return

        if size is None:
            size = self._estimate_size(value)

        full_key = f"{namespace}:{key}"
        cache.set(full_key, value, size)

        # Track for path-based invalidation
        self._track_path_key(key, level, full_key)

    def invalidate(
        self,
        namespace: str,
        key: str,
        level: Optional[CacheLevel] = None
    ) -> bool:
        """Invalidate cache entry.

        Args:
            namespace: Cache namespace
            key: Cache key
            level: Specific level or None for all levels

        Returns:
            True if any entry was invalidated
        """
        full_key = f"{namespace}:{key}"
        invalidated = False

        if level:
            cache = self.caches.get(level)
            if cache:
                invalidated = cache.invalidate(full_key)
        else:
            # Invalidate across all levels
            for cache in self.caches.values():
                if cache.invalidate(full_key):
                    invalidated = True

        return invalidated

    def invalidate_path(self, path: str) -> int:
        """Invalidate all entries related to a path.

        Args:
            path: File system path

        Returns:
            Number of entries invalidated
        """
        count = 0

        with self._path_lock:
            if path in self._path_keys:
                for level, full_key in self._path_keys[path].copy():
                    cache = self.caches.get(level)
                    if cache and cache.invalidate(full_key):
                        count += 1

                # Clean up tracking
                del self._path_keys[path]

        # Also invalidate any parent paths
        parent = self._get_parent_path(path)
        if parent and parent != path:
            count += self.invalidate_path(parent)

        return count

    def clear(self, level: Optional[CacheLevel] = None) -> None:
        """Clear cache.

        Args:
            level: Specific level or None for all levels
        """
        if level:
            cache = self.caches.get(level)
            if cache:
                cache.clear()
        else:
            for cache in self.caches.values():
                cache.clear()

        # Clear path tracking if clearing all
        if level is None:
            with self._path_lock:
                self._path_keys.clear()

    def get_stats(self, level: Optional[CacheLevel] = None) -> Dict[str, Any]:
        """Get cache statistics.

        Args:
            level: Specific level or None for all levels

        Returns:
            Cache statistics
        """
        if level:
            cache = self.caches.get(level)
            return cache.get_stats() if cache else {}

        # Aggregate stats across all levels
        stats = {}
        for cache_level, cache in self.caches.items():
            stats[cache_level.value] = cache.get_stats()

        # Add totals
        totals = {
            "total_entries": 0,
            "total_size_bytes": 0,
            "total_hits": 0,
            "total_misses": 0,
        }

        for level_stats in stats.values():
            totals["total_entries"] += level_stats["entries"]
            totals["total_size_bytes"] += level_stats["size_bytes"]
            totals["total_hits"] += level_stats["hits"]
            totals["total_misses"] += level_stats["misses"]

        total_requests = totals["total_hits"] + totals["total_misses"]
        totals["overall_hit_rate"] = (
            totals["total_hits"] / total_requests if total_requests > 0 else 0
        )

        stats["totals"] = totals
        return stats

    def warmup(
        self,
        namespace: str,
        entries: List[Tuple[str, Any, Optional[int]]],
        level: CacheLevel = CacheLevel.L2
    ) -> int:
        """Warm up cache with pre-loaded entries.

        Args:
            namespace: Cache namespace
            entries: List of (key, value, size) tuples
            level: Cache level

        Returns:
            Number of entries added
        """
        count = 0
        for key, value, size in entries:
            self.set(namespace, key, value, size, level)
            count += 1
        return count

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of a value in bytes.

        Args:
            value: Value to estimate

        Returns:
            Estimated size in bytes
        """
        if isinstance(value, (str, bytes)):
            return len(value)
        elif isinstance(value, (int, float)):
            return 8
        elif isinstance(value, bool):
            return 1
        elif isinstance(value, (list, tuple)):
            return sum(self._estimate_size(item) for item in value) + 8
        elif isinstance(value, dict):
            size = 8
            for k, v in value.items():
                size += self._estimate_size(k) + self._estimate_size(v)
            return size
        else:
            # Default estimate for unknown types
            return 256

    def _track_path_key(self, path: str, level: CacheLevel, full_key: str) -> None:
        """Track cache key for path-based invalidation.

        Args:
            path: File system path
            level: Cache level
            full_key: Full cache key
        """
        with self._path_lock:
            if path not in self._path_keys:
                self._path_keys[path] = set()
            self._path_keys[path].add((level, full_key))

    def _get_parent_path(self, path: str) -> Optional[str]:
        """Get parent path.

        Args:
            path: File system path

        Returns:
            Parent path or None
        """
        if "/" not in path:
            return None

        parts = path.rsplit("/", 1)
        if len(parts) == 2:
            return parts[0] or "/"
        return None


# Global cache manager instance
_global_cache: Optional[CacheManager] = None


def get_cache_manager(
    configs: Optional[Dict[CacheLevel, CacheConfig]] = None
) -> CacheManager:
    """Get or create global cache manager.

    Args:
        configs: Cache configurations

    Returns:
        Global cache manager
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager(configs)
    return _global_cache


def set_global_cache(cache: CacheManager) -> None:
    """Set the global cache manager.

    Args:
        cache: Cache manager to use globally
    """
    global _global_cache
    _global_cache = cache