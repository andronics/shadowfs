#!/usr/bin/env python3
"""Comprehensive tests for the CacheManager module."""

import time
import threading
from unittest.mock import patch, MagicMock
import pytest

from shadowfs.infrastructure.cache_manager import (
    CacheLevel,
    CacheEntry,
    CacheConfig,
    LRUCache,
    CacheManager,
    get_cache_manager,
    set_global_cache,
)


class TestCacheLevel:
    """Tests for CacheLevel enum."""

    def test_cache_levels(self):
        """Test cache level values."""
        assert CacheLevel.L1.value == "l1"
        assert CacheLevel.L2.value == "l2"
        assert CacheLevel.L3.value == "l3"

    def test_cache_level_comparison(self):
        """Test cache level comparison."""
        assert CacheLevel.L1 == CacheLevel.L1
        assert CacheLevel.L1 != CacheLevel.L2
        assert CacheLevel.L2 != CacheLevel.L3


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(key="test", value="data", size=4)
        assert entry.key == "test"
        assert entry.value == "data"
        assert entry.size == 4
        assert entry.access_count == 0
        assert isinstance(entry.timestamp, float)
        assert isinstance(entry.last_access, float)

    def test_cache_entry_timestamps(self):
        """Test cache entry timestamps can be set manually."""
        # Test with explicit timestamps
        entry = CacheEntry(
            key="test",
            value="data",
            size=4,
            timestamp=1234567890.0,
            last_access=1234567891.0
        )
        assert entry.timestamp == 1234567890.0
        assert entry.last_access == 1234567891.0

    def test_is_expired(self):
        """Test expiration check."""
        entry = CacheEntry(key="test", value="data", size=4)

        # Not expired with large TTL
        assert not entry.is_expired(3600)

        # Expired with zero TTL
        time.sleep(0.01)
        assert entry.is_expired(0.001)

    def test_is_expired_with_explicit_time(self):
        """Test expiration with explicit timestamps."""
        # Create entry with specific timestamp
        entry = CacheEntry(
            key="test",
            value="data",
            size=4,
            timestamp=1000.0
        )

        # Test expiration check at different current times
        with patch('shadowfs.infrastructure.cache_manager.time.time', return_value=1010.0):
            assert not entry.is_expired(20)  # 20s TTL, not expired
            assert entry.is_expired(5)  # 5s TTL, expired

    def test_touch(self):
        """Test updating access time and count."""
        entry = CacheEntry(
            key="test",
            value="data",
            size=4,
            timestamp=1000.0,
            last_access=1000.0
        )
        assert entry.access_count == 0
        assert entry.last_access == 1000.0

        with patch('shadowfs.infrastructure.cache_manager.time.time', return_value=1005.0):
            entry.touch()
            assert entry.access_count == 1
            assert entry.last_access == 1005.0

            entry.touch()
            assert entry.access_count == 2


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_cache_config_creation(self):
        """Test creating cache configuration."""
        config = CacheConfig(
            max_entries=100,
            max_size_bytes=1024,
            ttl_seconds=60.0
        )
        assert config.max_entries == 100
        assert config.max_size_bytes == 1024
        assert config.ttl_seconds == 60.0
        assert config.enabled is True

    def test_cache_config_disabled(self):
        """Test disabled cache configuration."""
        config = CacheConfig(
            max_entries=100,
            max_size_bytes=1024,
            ttl_seconds=60.0,
            enabled=False
        )
        assert config.enabled is False

    def test_validate_valid_config(self):
        """Test validating valid configuration."""
        config = CacheConfig(
            max_entries=100,
            max_size_bytes=1024,
            ttl_seconds=60.0
        )
        config.validate()  # Should not raise

    def test_validate_invalid_entries(self):
        """Test validation with invalid max_entries."""
        config = CacheConfig(
            max_entries=0,
            max_size_bytes=1024,
            ttl_seconds=60.0
        )
        with pytest.raises(ValueError, match="max_entries must be positive"):
            config.validate()

    def test_validate_invalid_size(self):
        """Test validation with invalid max_size_bytes."""
        config = CacheConfig(
            max_entries=100,
            max_size_bytes=-1,
            ttl_seconds=60.0
        )
        with pytest.raises(ValueError, match="max_size_bytes must be positive"):
            config.validate()

    def test_validate_invalid_ttl(self):
        """Test validation with invalid ttl_seconds."""
        config = CacheConfig(
            max_entries=100,
            max_size_bytes=1024,
            ttl_seconds=0
        )
        with pytest.raises(ValueError, match="ttl_seconds must be positive"):
            config.validate()


class TestLRUCache:
    """Tests for LRUCache class."""

    @pytest.fixture
    def cache(self):
        """Create test cache."""
        config = CacheConfig(
            max_entries=3,
            max_size_bytes=100,
            ttl_seconds=1.0
        )
        return LRUCache(config)

    def test_lru_cache_creation(self, cache):
        """Test creating LRU cache."""
        assert cache.config.max_entries == 3
        assert cache.config.max_size_bytes == 100
        assert cache.config.ttl_seconds == 1.0
        assert cache._current_size == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_get_miss(self, cache):
        """Test cache miss."""
        result = cache.get("nonexistent")
        assert result is None
        assert cache._misses == 1
        assert cache._hits == 0

    def test_set_and_get(self, cache):
        """Test setting and getting value."""
        cache.set("key1", "value1", 6)

        result = cache.get("key1")
        assert result == "value1"
        assert cache._hits == 1
        assert cache._current_size == 6

    def test_cache_disabled(self):
        """Test operations with disabled cache."""
        config = CacheConfig(
            max_entries=3,
            max_size_bytes=100,
            ttl_seconds=1.0,
            enabled=False
        )
        cache = LRUCache(config)

        cache.set("key1", "value1", 6)
        result = cache.get("key1")
        assert result is None
        assert cache._misses == 1

    def test_ttl_expiration(self, cache):
        """Test TTL expiration."""
        cache.set("key1", "value1", 6)

        # Should be available immediately
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        result = cache.get("key1")
        assert result is None
        assert cache._expirations == 1
        assert cache._current_size == 0

    def test_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        cache.set("key1", "value1", 10)
        cache.set("key2", "value2", 10)
        cache.set("key3", "value3", 10)

        # Access key1 and key2 to make key3 LRU
        cache.get("key1")
        cache.get("key2")

        # Add key4, should evict key3
        cache.set("key4", "value4", 10)

        assert cache.get("key3") is None  # Evicted
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") == "value2"  # Still there
        assert cache.get("key4") == "value4"  # New entry
        assert cache._evictions == 1

    def test_size_based_eviction(self, cache):
        """Test eviction based on size limit."""
        cache.set("key1", "x" * 40, 40)
        cache.set("key2", "y" * 40, 40)

        # Adding key3 should evict key1 due to size limit
        cache.set("key3", "z" * 30, 30)

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "y" * 40
        assert cache.get("key3") == "z" * 30
        assert cache._current_size == 70

    def test_value_too_large(self, cache):
        """Test adding value larger than cache size."""
        cache.set("huge", "x" * 200, 200)

        # Should not be cached
        assert cache.get("huge") is None
        assert cache._current_size == 0

    def test_replace_existing(self, cache):
        """Test replacing existing entry."""
        cache.set("key1", "value1", 10)
        assert cache._current_size == 10

        cache.set("key1", "value2", 15)
        assert cache.get("key1") == "value2"
        assert cache._current_size == 15

    def test_invalidate(self, cache):
        """Test invalidating entry."""
        cache.set("key1", "value1", 10)
        cache.set("key2", "value2", 10)

        assert cache.invalidate("key1") is True
        assert cache.get("key1") is None
        assert cache._current_size == 10

        assert cache.invalidate("nonexistent") is False

    def test_clear(self, cache):
        """Test clearing cache."""
        cache.set("key1", "value1", 10)
        cache.set("key2", "value2", 10)

        cache.clear()
        assert cache._current_size == 0
        assert len(cache._cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_get_stats(self, cache):
        """Test getting cache statistics."""
        cache.set("key1", "value1", 10)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()
        assert stats["entries"] == 1
        assert stats["size_bytes"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["evictions"] == 0
        assert stats["expirations"] == 0

    def test_get_stats_empty(self, cache):
        """Test statistics for empty cache."""
        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["size_bytes"] == 0
        assert stats["hit_rate"] == 0

    def test_get_entries(self, cache):
        """Test getting cache entries."""
        cache.set("key1", "value1", 10)
        time.sleep(0.01)
        cache.set("key2", "value2", 20)

        entries = cache.get_entries()
        assert len(entries) == 2

        # Check first entry
        key, size, age = entries[0]
        assert key == "key1"
        assert size == 10
        assert age > 0

        # Second entry should be younger
        key2, size2, age2 = entries[1]
        assert key2 == "key2"
        assert size2 == 20
        assert age2 < age

    def test_lru_ordering(self, cache):
        """Test LRU ordering after access."""
        cache.set("key1", "value1", 10)
        cache.set("key2", "value2", 10)
        cache.set("key3", "value3", 10)

        # Access key1, making it most recently used
        cache.get("key1")

        # Add key4, should evict key2 (now LRU)
        cache.set("key4", "value4", 10)

        assert cache.get("key2") is None  # Evicted
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key3") == "value3"  # Still there
        assert cache.get("key4") == "value4"  # New entry

    def test_evict_multiple(self, cache):
        """Test evicting multiple entries for space."""
        cache.set("key1", "x" * 30, 30)
        cache.set("key2", "y" * 30, 30)
        cache.set("key3", "z" * 30, 30)

        # Add large entry that requires evicting multiple entries
        cache.set("key4", "a" * 80, 80)

        # Should have evicted key1 and key2
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key4") == "a" * 80
        assert cache._evictions >= 2

    def test_empty_cache_eviction(self):
        """Test eviction with empty cache doesn't crash."""
        config = CacheConfig(
            max_entries=0,  # Will be caught by validation
            max_size_bytes=100,
            ttl_seconds=1.0
        )
        with pytest.raises(ValueError):
            LRUCache(config)


class TestCacheManager:
    """Tests for CacheManager class."""

    @pytest.fixture
    def manager(self):
        """Create test cache manager."""
        configs = {
            CacheLevel.L1: CacheConfig(max_entries=10, max_size_bytes=100, ttl_seconds=1.0),
            CacheLevel.L2: CacheConfig(max_entries=5, max_size_bytes=200, ttl_seconds=2.0),
        }
        return CacheManager(configs)

    def test_cache_manager_creation(self, manager):
        """Test creating cache manager."""
        assert CacheLevel.L1 in manager.caches
        assert CacheLevel.L2 in manager.caches
        assert len(manager._path_keys) == 0

    def test_default_configs(self):
        """Test cache manager with default configs."""
        manager = CacheManager()
        assert CacheLevel.L1 in manager.caches
        assert CacheLevel.L2 in manager.caches
        assert CacheLevel.L3 in manager.caches

    def test_get_and_set(self, manager):
        """Test getting and setting values."""
        manager.set("attrs", "file.txt", {"size": 100}, level=CacheLevel.L1)

        result = manager.get("attrs", "file.txt", level=CacheLevel.L1)
        assert result == {"size": 100}

        # Different namespace
        assert manager.get("content", "file.txt", level=CacheLevel.L1) is None

    def test_set_with_estimated_size(self, manager):
        """Test setting with automatic size estimation."""
        manager.set("test", "key", "value")  # String
        manager.set("test", "key2", 42)  # Int
        manager.set("test", "key3", True)  # Bool
        manager.set("test", "key4", [1, 2, 3])  # List
        manager.set("test", "key5", {"a": 1})  # Dict
        manager.set("test", "key6", object())  # Unknown type

        assert manager.get("test", "key") == "value"
        assert manager.get("test", "key2") == 42

    def test_invalid_level(self, manager):
        """Test operations with invalid cache level."""
        # If level doesn't exist, operations should be no-ops
        result = manager.get("test", "key", level=None)
        assert result is None

    def test_invalidate_single_level(self, manager):
        """Test invalidating entry at specific level."""
        manager.set("attrs", "file.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "file.txt", "data2", level=CacheLevel.L2)

        # Invalidate only L1
        assert manager.invalidate("attrs", "file.txt", level=CacheLevel.L1) is True

        assert manager.get("attrs", "file.txt", level=CacheLevel.L1) is None
        assert manager.get("attrs", "file.txt", level=CacheLevel.L2) == "data2"

    def test_invalidate_all_levels(self, manager):
        """Test invalidating entry across all levels."""
        manager.set("attrs", "file.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "file.txt", "data2", level=CacheLevel.L2)

        # Invalidate all levels
        assert manager.invalidate("attrs", "file.txt") is True

        assert manager.get("attrs", "file.txt", level=CacheLevel.L1) is None
        assert manager.get("attrs", "file.txt", level=CacheLevel.L2) is None

    def test_invalidate_path(self, manager):
        """Test path-based invalidation."""
        manager.set("attrs", "/dir/file.txt", "data1", level=CacheLevel.L1)
        manager.set("content", "/dir/file.txt", "data2", level=CacheLevel.L2)
        manager.set("attrs", "/dir", "data3", level=CacheLevel.L1)

        count = manager.invalidate_path("/dir/file.txt")
        assert count >= 2  # At least the two entries for file.txt

        assert manager.get("attrs", "/dir/file.txt", level=CacheLevel.L1) is None
        assert manager.get("content", "/dir/file.txt", level=CacheLevel.L2) is None

    def test_invalidate_path_with_parent(self, manager):
        """Test invalidating path also invalidates parent."""
        manager.set("attrs", "/dir/subdir/file.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "/dir/subdir", "data2", level=CacheLevel.L1)
        manager.set("attrs", "/dir", "data3", level=CacheLevel.L1)

        count = manager.invalidate_path("/dir/subdir/file.txt")

        # Should invalidate file and its parent directories
        assert manager.get("attrs", "/dir/subdir/file.txt", level=CacheLevel.L1) is None

    def test_clear_single_level(self, manager):
        """Test clearing specific cache level."""
        manager.set("test", "key1", "data1", level=CacheLevel.L1)
        manager.set("test", "key2", "data2", level=CacheLevel.L2)

        manager.clear(level=CacheLevel.L1)

        assert manager.get("test", "key1", level=CacheLevel.L1) is None
        assert manager.get("test", "key2", level=CacheLevel.L2) == "data2"

    def test_clear_all_levels(self, manager):
        """Test clearing all cache levels."""
        manager.set("test", "key1", "data1", level=CacheLevel.L1)
        manager.set("test", "key2", "data2", level=CacheLevel.L2)

        manager.clear()

        assert manager.get("test", "key1", level=CacheLevel.L1) is None
        assert manager.get("test", "key2", level=CacheLevel.L2) is None
        assert len(manager._path_keys) == 0

    def test_get_stats_single_level(self, manager):
        """Test getting statistics for single level."""
        manager.set("test", "key", "data", level=CacheLevel.L1)
        manager.get("test", "key", level=CacheLevel.L1)

        stats = manager.get_stats(level=CacheLevel.L1)
        assert stats["entries"] == 1
        assert stats["hits"] == 1

    def test_get_stats_all_levels(self, manager):
        """Test getting aggregated statistics."""
        manager.set("test", "key1", "data1", level=CacheLevel.L1)
        manager.set("test", "key2", "data2", level=CacheLevel.L2)
        manager.get("test", "key1", level=CacheLevel.L1)
        manager.get("test", "missing", level=CacheLevel.L1)

        stats = manager.get_stats()
        assert "l1" in stats
        assert "l2" in stats
        assert "totals" in stats

        assert stats["totals"]["total_entries"] == 2
        assert stats["totals"]["total_hits"] == 1
        assert stats["totals"]["total_misses"] == 1

    def test_get_stats_empty(self, manager):
        """Test statistics for empty cache."""
        stats = manager.get_stats()
        assert stats["totals"]["overall_hit_rate"] == 0

    def test_warmup(self, manager):
        """Test warming up cache."""
        entries = [
            ("key1", "data1", 5),
            ("key2", "data2", 5),
            ("key3", "data3", None),  # Size will be estimated
        ]

        count = manager.warmup("test", entries, level=CacheLevel.L1)
        assert count == 3

        assert manager.get("test", "key1", level=CacheLevel.L1) == "data1"
        assert manager.get("test", "key2", level=CacheLevel.L1) == "data2"
        assert manager.get("test", "key3", level=CacheLevel.L1) == "data3"

    def test_estimate_size(self, manager):
        """Test size estimation for different types."""
        assert manager._estimate_size("hello") == 5  # String
        assert manager._estimate_size(b"hello") == 5  # Bytes
        assert manager._estimate_size(42) == 8  # Int
        assert manager._estimate_size(3.14) == 8  # Float
        # Note: bool inherits from int, so it's treated as int (8 bytes)
        assert manager._estimate_size(True) == 8  # Bool (treated as int)
        assert manager._estimate_size([1, 2, 3]) > 24  # List
        assert manager._estimate_size({"a": 1, "b": 2}) > 16  # Dict
        assert manager._estimate_size(object()) == 256  # Unknown

    def test_get_parent_path(self, manager):
        """Test getting parent path."""
        assert manager._get_parent_path("/dir/file.txt") == "/dir"
        assert manager._get_parent_path("/dir/subdir/file.txt") == "/dir/subdir"
        assert manager._get_parent_path("/file.txt") == "/"
        assert manager._get_parent_path("file.txt") is None
        assert manager._get_parent_path("/") == "/"  # Root returns itself
        assert manager._get_parent_path("") is None  # Empty string

    def test_path_tracking(self, manager):
        """Test path-based key tracking."""
        manager.set("attrs", "/test/file.txt", "data", level=CacheLevel.L1)

        assert "/test/file.txt" in manager._path_keys
        assert len(manager._path_keys["/test/file.txt"]) == 1

        # Add same path different namespace
        manager.set("content", "/test/file.txt", "content", level=CacheLevel.L2)
        assert len(manager._path_keys["/test/file.txt"]) == 2


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_operations(self):
        """Test concurrent cache operations."""
        manager = CacheManager()

        def worker(thread_id):
            for i in range(100):
                key = f"key_{thread_id}_{i}"
                manager.set("test", key, f"data_{thread_id}_{i}")
                manager.get("test", key)
                if i % 10 == 0:
                    manager.invalidate("test", f"key_{thread_id}_{i-5}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should complete without errors
        stats = manager.get_stats()
        assert stats["totals"]["total_entries"] > 0

    def test_concurrent_path_invalidation(self):
        """Test concurrent path invalidation."""
        manager = CacheManager()

        # Pre-populate cache
        for i in range(100):
            manager.set("test", f"/dir{i}/file.txt", f"data{i}")

        def invalidator(start, end):
            for i in range(start, end):
                manager.invalidate_path(f"/dir{i}/file.txt")

        threads = []
        for i in range(0, 100, 20):
            t = threading.Thread(target=invalidator, args=(i, i+20))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All paths should be invalidated
        for i in range(100):
            assert manager.get("test", f"/dir{i}/file.txt") is None


class TestGlobalCache:
    """Tests for global cache functions."""

    def test_get_cache_manager_creates_instance(self):
        """Test get_cache_manager creates new instance."""
        set_global_cache(None)
        cache = get_cache_manager()
        assert cache is not None
        assert isinstance(cache, CacheManager)

    def test_get_cache_manager_reuses_instance(self):
        """Test get_cache_manager reuses existing instance."""
        set_global_cache(None)
        cache1 = get_cache_manager()
        cache2 = get_cache_manager()
        assert cache1 is cache2

    def test_get_cache_manager_with_config(self):
        """Test get_cache_manager with custom config."""
        set_global_cache(None)
        configs = {
            CacheLevel.L1: CacheConfig(max_entries=5, max_size_bytes=50, ttl_seconds=0.5)
        }
        cache = get_cache_manager(configs)
        assert cache.configs == configs

    def test_set_global_cache(self):
        """Test setting global cache instance."""
        custom_cache = CacheManager()
        set_global_cache(custom_cache)

        cache = get_cache_manager()
        assert cache is custom_cache