#!/usr/bin/env python3
"""Transform pipeline for chaining content transformations.

This module provides pipeline execution for transforms:
- Sequential transform chaining
- Error handling with graceful degradation
- Transform caching for performance
- Conditional transform application
- Pipeline statistics and monitoring

Example:
    >>> pipeline = TransformPipeline()
    >>> pipeline.add_transform(CompressionTransform())
    >>> pipeline.add_transform(EncryptionTransform())
    >>> result = pipeline.apply(content, "file.txt")
"""

import hashlib
import threading
from typing import Any, Dict, List, Optional

from shadowfs.core.cache import CacheManager
from shadowfs.core.logging import get_logger
from shadowfs.transforms.base import Transform, TransformResult


class TransformPipeline:
    """Pipeline for chaining multiple transforms.

    Features:
    - Sequential transform execution
    - Graceful error handling (continue or halt)
    - Transform result caching
    - Conditional transform application
    - Performance monitoring
    """

    def __init__(
        self,
        cache_enabled: bool = True,
        cache_ttl: int = 300,
        halt_on_error: bool = False,
    ):
        """Initialize transform pipeline.

        Args:
            cache_enabled: Enable transform result caching
            cache_ttl: Cache TTL in seconds
            halt_on_error: Stop pipeline on first error (vs continue)
        """
        self._transforms: List[Transform] = []
        self._lock = threading.RLock()
        self._cache_enabled = cache_enabled
        self._halt_on_error = halt_on_error
        self._logger = get_logger()

        # Initialize cache if enabled
        if cache_enabled:
            from shadowfs.core.cache import CacheConfig, CacheLevel

            cache_config = CacheConfig(
                max_entries=10000,
                max_size_bytes=256 * 1024 * 1024,  # 256 MB
                ttl_seconds=cache_ttl,
                enabled=True,
            )
            # Create simple single-level cache manager
            self._cache = CacheManager(configs={CacheLevel.L3: cache_config})
        else:
            self._cache = None

        self._stats = {
            "total_pipelines": 0,
            "successful_pipelines": 0,
            "failed_pipelines": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    def add_transform(self, transform: Transform) -> None:
        """Add transform to pipeline.

        Transforms are executed in order they are added.

        Args:
            transform: Transform to add
        """
        with self._lock:
            self._transforms.append(transform)

    def remove_transform(self, name: str) -> bool:
        """Remove transform by name.

        Args:
            name: Transform name

        Returns:
            True if transform was removed
        """
        with self._lock:
            for i, transform in enumerate(self._transforms):
                if transform.name == name:
                    self._transforms.pop(i)
                    return True
        return False

    def clear_transforms(self) -> None:
        """Remove all transforms from pipeline."""
        with self._lock:
            self._transforms.clear()

    def get_transforms(self) -> List[Transform]:
        """Get all transforms in pipeline.

        Returns:
            List of transforms (copy)
        """
        with self._lock:
            return self._transforms.copy()

    def apply(
        self,
        content: bytes,
        path: str,
        metadata: Optional[Dict[str, Any]] = None,
        skip_cache: bool = False,
    ) -> TransformResult:
        """Apply all transforms in pipeline.

        Args:
            content: Input content
            path: File path
            metadata: Optional metadata
            skip_cache: Skip cache lookup/storage

        Returns:
            Final transform result
        """
        if not self._transforms:
            # No transforms, return original content
            return TransformResult(
                content=content,
                success=True,
                metadata={"transforms_applied": 0},
            )

        # Check cache first
        if self._cache_enabled and not skip_cache:
            cache_key = self._get_cache_key(content, path)
            from shadowfs.core.cache import CacheLevel

            cached = self._cache.get("transform", cache_key, CacheLevel.L3)
            if cached is not None:
                self._stats["cache_hits"] += 1
                self._logger.debug(f"Transform cache hit for {path}")
                return cached
            self._stats["cache_misses"] += 1

        # Apply transforms sequentially
        current_content = content
        transform_results = []
        all_success = True

        with self._lock:
            transforms = self._transforms.copy()

        for transform in transforms:
            if not transform.enabled:
                continue

            if not transform.supports(path, metadata):
                continue

            # Apply transform
            result = transform.apply(current_content, path, metadata)
            transform_results.append(
                {
                    "name": transform.name,
                    "success": result.success,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                }
            )

            if result.success:
                current_content = result.content
            else:
                all_success = False
                if self._halt_on_error:
                    # Stop pipeline on error
                    break

        # Create final result
        final_result = TransformResult(
            content=current_content,
            success=all_success,
            metadata={
                "transforms_applied": len(transform_results),
                "transform_results": transform_results,
                "pipeline_halted": not all_success and self._halt_on_error,
            },
        )

        # Update stats
        self._stats["total_pipelines"] += 1
        if all_success:
            self._stats["successful_pipelines"] += 1
        else:
            self._stats["failed_pipelines"] += 1

        # Cache result if successful
        if self._cache_enabled and not skip_cache and all_success:
            cache_key = self._get_cache_key(content, path)
            from shadowfs.core.cache import CacheLevel

            # Estimate size
            result_size = len(final_result.content) + 1024  # Content + metadata overhead
            self._cache.set("transform", cache_key, final_result, result_size, CacheLevel.L3)

        return final_result

    def _get_cache_key(self, content: bytes, path: str) -> str:
        """Generate cache key for content + path + transforms.

        Args:
            content: Input content
            path: File path

        Returns:
            Cache key string
        """
        # Hash content
        content_hash = hashlib.sha256(content).hexdigest()[:16]

        # Hash transform configuration
        with self._lock:
            transform_config = "|".join(f"{t.name}:{t.enabled}" for t in self._transforms)
        config_hash = hashlib.sha256(transform_config.encode()).hexdigest()[:8]

        return f"transform:{path}:{content_hash}:{config_hash}"

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics.

        Returns:
            Statistics dictionary
        """
        stats = self._stats.copy()

        # Add transform-level stats
        with self._lock:
            stats["transform_stats"] = {t.name: t.get_stats() for t in self._transforms}

        # Calculate cache hit rate
        total_cache_ops = stats["cache_hits"] + stats["cache_misses"]
        if total_cache_ops > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / total_cache_ops
        else:
            stats["cache_hit_rate"] = 0.0

        return stats

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._stats = {
            "total_pipelines": 0,
            "successful_pipelines": 0,
            "failed_pipelines": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        with self._lock:
            for transform in self._transforms:
                transform.reset_stats()

    def clear_cache(self) -> None:
        """Clear transform cache."""
        if self._cache:
            from shadowfs.core.cache import CacheLevel

            self._cache.clear(CacheLevel.L3)

    def enable_transform(self, name: str) -> bool:
        """Enable transform by name.

        Args:
            name: Transform name

        Returns:
            True if transform was found
        """
        with self._lock:
            for transform in self._transforms:
                if transform.name == name:
                    transform.enable()
                    return True
        return False

    def disable_transform(self, name: str) -> bool:
        """Disable transform by name.

        Args:
            name: Transform name

        Returns:
            True if transform was found
        """
        with self._lock:
            for transform in self._transforms:
                if transform.name == name:
                    transform.disable()
                    return True
        return False

    def __len__(self) -> int:
        """Return number of transforms in pipeline."""
        with self._lock:
            return len(self._transforms)

    def __repr__(self) -> str:
        """String representation."""
        with self._lock:
            transform_names = [t.name for t in self._transforms]
        return f"<TransformPipeline transforms={transform_names}>"
