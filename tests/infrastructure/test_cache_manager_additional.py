#!/usr/bin/env python3
"""Additional tests for complete CacheManager coverage."""

import threading
import pytest

from shadowfs.infrastructure.cache_manager import (
    CacheLevel,
    CacheEntry,
    CacheConfig,
    LRUCache,
    CacheManager,
)


class TestAdditionalCoverage:
    """Tests for additional coverage."""

    def test_lru_cache_with_empty_cache_eviction(self):
        """Test eviction when cache becomes empty."""
        config = CacheConfig(
            max_entries=2,
            max_size_bytes=50,
            ttl_seconds=1.0
        )
        cache = LRUCache(config)

        # Add and remove all entries
        cache.set("key1", "value1", 10)
        cache.clear()

        # Try to evict from empty cache
        cache._evict_lru()  # Should not crash

        # Verify cache is still empty
        assert len(cache._cache) == 0

    def test_remove_entry_nonexistent(self):
        """Test removing non-existent entry."""
        config = CacheConfig(
            max_entries=2,
            max_size_bytes=50,
            ttl_seconds=1.0
        )
        cache = LRUCache(config)

        # Try to remove non-existent entry
        cache._remove_entry("nonexistent")  # Should not crash
        assert cache._current_size == 0

    def test_evict_when_cache_empty_during_set(self):
        """Test eviction branch when cache becomes empty during set."""
        config = CacheConfig(
            max_entries=1,
            max_size_bytes=10,
            ttl_seconds=1.0
        )
        cache = LRUCache(config)

        # Try to add item larger than cache
        cache.set("key", "x" * 20, 20)  # Too large, won't be cached

        # Cache should remain empty
        assert len(cache._cache) == 0

    def test_cache_manager_no_caches_for_level(self):
        """Test operations when cache level doesn't exist."""
        manager = CacheManager({})  # No caches configured

        # Use a level that definitely doesn't exist
        # Since we pass empty dict, no levels exist
        fake_level = None  # Use None as a non-existent level

        # Get from non-existent level
        assert manager.get("test", "key", level=fake_level) is None

        # Set to non-existent level (should be no-op)
        manager.set("test", "key", "value", level=fake_level)

        # Verify nothing was set
        assert manager.get("test", "key", level=fake_level) is None

        # Clear non-existent level
        manager.clear(level=fake_level)  # Should not crash

    def test_cache_manager_get_stats_no_cache(self):
        """Test getting stats for non-existent cache level."""
        manager = CacheManager({})

        # Use None as non-existent level
        stats = manager.get_stats(level=None)
        # Should return aggregated stats with empty totals
        assert "totals" in stats
        assert stats["totals"]["total_entries"] == 0

    def test_invalidate_path_no_parent(self):
        """Test invalidating path with no parent."""
        manager = CacheManager()

        # Set entry with path that has no parent
        manager.set("test", "file.txt", "data", level=CacheLevel.L1)

        # Invalidate - should not try to invalidate parent
        count = manager.invalidate_path("file.txt")
        assert count >= 1

    def test_invalidate_path_recursive_parent(self):
        """Test recursive parent invalidation."""
        manager = CacheManager()

        # Set entries at multiple levels
        manager.set("attrs", "/a/b/c/d/file.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "/a/b/c/d", "data2", level=CacheLevel.L1)
        manager.set("attrs", "/a/b/c", "data3", level=CacheLevel.L1)

        # Invalidate deepest path - should recursively invalidate parents
        count = manager.invalidate_path("/a/b/c/d/file.txt")
        assert count >= 1  # At least the file itself

    def test_path_already_tracked(self):
        """Test adding same path multiple times."""
        manager = CacheManager()

        # Set same path multiple times with different namespaces
        manager.set("attrs", "/test/file.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "/test/file.txt", "data2", level=CacheLevel.L1)  # Replace
        manager.set("content", "/test/file.txt", "data3", level=CacheLevel.L2)

        # Path should be tracked with multiple keys
        assert "/test/file.txt" in manager._path_keys

    def test_invalidate_nonexistent_from_all_levels(self):
        """Test invalidating non-existent key from all levels."""
        manager = CacheManager()

        # Try to invalidate non-existent key from all levels
        result = manager.invalidate("namespace", "nonexistent")
        assert result is False

    def test_eviction_loop_break(self):
        """Test break condition in eviction loop."""
        config = CacheConfig(
            max_entries=1,
            max_size_bytes=100,
            ttl_seconds=1.0
        )
        cache = LRUCache(config)

        # Clear cache to make it empty
        cache.clear()

        # Try to set with empty cache needing eviction
        # This tests the break condition in the while loop
        cache.set("key", "value", 10)
        assert cache.get("key") == "value"

    def test_invalidate_path_cleans_tracking(self):
        """Test that invalidate_path cleans up tracking."""
        manager = CacheManager()

        # Set and track a path
        manager.set("attrs", "/test/file.txt", "data", level=CacheLevel.L1)
        assert "/test/file.txt" in manager._path_keys

        # Invalidate should clean up tracking
        manager.invalidate_path("/test/file.txt")
        assert "/test/file.txt" not in manager._path_keys

    def test_clear_all_clears_path_tracking(self):
        """Test that clearing all levels clears path tracking."""
        manager = CacheManager()

        # Set some paths
        manager.set("attrs", "/test/file1.txt", "data1", level=CacheLevel.L1)
        manager.set("attrs", "/test/file2.txt", "data2", level=CacheLevel.L2)
        assert len(manager._path_keys) > 0

        # Clear all should clear path tracking
        manager.clear()
        assert len(manager._path_keys) == 0

    def test_get_parent_path_edge_cases(self):
        """Test edge cases for parent path extraction."""
        manager = CacheManager()

        # Test root variations
        assert manager._get_parent_path("/") == "/"

        # Test paths with trailing slashes (rsplit removes trailing slash)
        assert manager._get_parent_path("/dir/") == "/dir"

        # Test multiple slashes
        assert manager._get_parent_path("//dir//file.txt") == "//dir"

    def test_estimate_size_nested_structures(self):
        """Test size estimation for nested structures."""
        manager = CacheManager()

        # Nested list
        nested_list = [[1, 2], [3, 4]]
        size = manager._estimate_size(nested_list)
        assert size > 32  # Should account for nested structure

        # Nested dict
        nested_dict = {"a": {"b": 1, "c": 2}, "d": {"e": 3}}
        size = manager._estimate_size(nested_dict)
        assert size > 24  # Should account for nested structure

        # Mixed types in list
        mixed = [1, "string", {"key": "value"}, [1, 2]]
        size = manager._estimate_size(mixed)
        assert size > 20

    def test_global_functions_coverage(self):
        """Test global function edge cases."""
        from shadowfs.infrastructure.cache_manager import get_cache_manager, set_global_cache

        # Clear global cache
        set_global_cache(None)

        # Create with custom config
        custom_config = {
            CacheLevel.L1: CacheConfig(max_entries=1, max_size_bytes=10, ttl_seconds=0.1)
        }
        cache1 = get_cache_manager(custom_config)

        # Second call should reuse instance (config ignored)
        cache2 = get_cache_manager()
        assert cache1 is cache2

        # But the first config was used
        assert cache1.configs == custom_config