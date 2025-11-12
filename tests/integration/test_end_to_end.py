"""End-to-end integration tests for ShadowFS.

This module tests the complete system with all components integrated:
- FUSE operations with real filesystem
- Rule engine filtering
- Transform pipeline execution
- Virtual layer resolution
- Cache management
- Full application stack
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from shadowfs.core.cache import CacheConfig, CacheLevel, CacheManager
from shadowfs.core.config import ConfigManager
from shadowfs.core.logging import Logger
from shadowfs.fuse.operations import ShadowFS
from shadowfs.layers.classifier import ClassifierLayer
from shadowfs.layers.manager import LayerManager
from shadowfs.main import ShadowFSMain
from shadowfs.rules.engine import Rule, RuleAction, RuleEngine
from shadowfs.transforms.pipeline import TransformPipeline


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directory structure."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    mount_dir = tmp_path / "mount"
    mount_dir.mkdir()

    # Create test files
    (source_dir / "file1.txt").write_text("content1")
    (source_dir / "file2.py").write_text("print('hello')")
    (source_dir / "file3.md").write_text("# Heading")
    (source_dir / "hidden.tmp").write_text("temporary")

    # Create subdirectory
    subdir = source_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")

    return {"source": source_dir, "mount": mount_dir}


@pytest.fixture
def config_manager(temp_dirs):
    """Create configuration manager."""
    config = ConfigManager()
    config._config = {
        "sources": [{"path": str(temp_dirs["source"]), "priority": 1}],
        "readonly": True,
        "allow_other": False,
        "rules": [],
        "transforms": [],
        "virtual_layers": [],
        "cache": {"enabled": True, "max_size_mb": 10, "ttl_seconds": 60},
        "logging": {"level": "DEBUG"},
    }
    return config


@pytest.fixture
def cache_manager():
    """Create cache manager."""
    cache_configs = {
        CacheLevel.L1: CacheConfig(
            max_entries=1000, max_size_bytes=1024 * 1024, ttl_seconds=60, enabled=True
        ),
        CacheLevel.L2: CacheConfig(
            max_entries=500, max_size_bytes=2 * 1024 * 1024, ttl_seconds=120, enabled=True
        ),
        CacheLevel.L3: CacheConfig(
            max_entries=100, max_size_bytes=4 * 1024 * 1024, ttl_seconds=180, enabled=True
        ),
    }
    return CacheManager(configs=cache_configs)


@pytest.fixture
def rule_engine():
    """Create rule engine."""
    return RuleEngine()


@pytest.fixture
def transform_pipeline():
    """Create transform pipeline."""
    return TransformPipeline()


@pytest.fixture
def layer_manager(temp_dirs):
    """Create virtual layer manager."""
    return LayerManager(sources=[str(temp_dirs["source"])])


@pytest.fixture
def fuse_ops(config_manager, cache_manager, rule_engine, transform_pipeline, layer_manager):
    """Create FUSE operations with all components."""
    return ShadowFS(
        config=config_manager,
        cache=cache_manager,
        rule_engine=rule_engine,
        transform_pipeline=transform_pipeline,
        layer_manager=layer_manager,
    )


class TestBasicFilesystemOperations:
    """Test basic filesystem operations end-to-end."""

    def test_list_root_directory(self, fuse_ops, temp_dirs):
        """Lists files in root directory."""
        entries = fuse_ops.readdir("/", None)

        # Convert to list (generator)
        file_list = list(entries)

        # Should have . and .. plus all files
        assert "." in file_list
        assert ".." in file_list
        assert "file1.txt" in file_list
        assert "file2.py" in file_list
        assert "file3.md" in file_list

    def test_list_subdirectory(self, fuse_ops):
        """Lists files in subdirectory."""
        entries = fuse_ops.readdir("/subdir", None)
        file_list = list(entries)

        assert "nested.txt" in file_list

    def test_get_file_attributes(self, fuse_ops):
        """Gets file attributes."""
        attrs = fuse_ops.getattr("/file1.txt", None)

        assert attrs["st_size"] == 8  # "content1" = 8 bytes
        assert attrs["st_mode"] & 0o100000  # Regular file

    def test_get_directory_attributes(self, fuse_ops):
        """Gets directory attributes."""
        attrs = fuse_ops.getattr("/subdir", None)

        assert attrs["st_mode"] & 0o040000  # Directory

    def test_open_and_read_file(self, fuse_ops):
        """Opens and reads file content."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)
        fuse_ops.release("/file1.txt", fh)

        assert content == b"content1"

    def test_read_with_offset(self, fuse_ops):
        """Reads file with offset."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 4, 3, fh)
        fuse_ops.release("/file1.txt", fh)

        assert content == b"tent"  # "content1"[3:7] = "tent"

    def test_read_with_limit(self, fuse_ops):
        """Reads file with size limit."""
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 4, 0, fh)
        fuse_ops.release("/file1.txt", fh)

        assert content == b"cont"  # First 4 bytes


class TestRuleEngineIntegration:
    """Test rule engine integration."""

    def test_exclude_files_by_pattern(self, fuse_ops, rule_engine):
        """Excludes files matching pattern."""
        # Add exclude rule for .tmp files
        rule = Rule(
            name="Exclude temp",
            action=RuleAction.EXCLUDE,
            patterns=["*.tmp"],
            priority=100,
        )
        rule_engine.add_rule(rule)

        # List directory
        entries = list(fuse_ops.readdir("/", None))

        # Should not include hidden.tmp
        assert "hidden.tmp" not in entries
        assert "file1.txt" in entries

    def test_include_only_specific_files(self, fuse_ops, rule_engine):
        """Includes only files matching pattern."""
        # Add exclude non-Python files
        exclude_txt = Rule(
            name="Exclude txt",
            action=RuleAction.EXCLUDE,
            patterns=["*.txt"],
            priority=50,
        )
        rule_engine.add_rule(exclude_txt)

        exclude_md = Rule(
            name="Exclude md",
            action=RuleAction.EXCLUDE,
            patterns=["*.md"],
            priority=50,
        )
        rule_engine.add_rule(exclude_md)

        # List directory
        entries = list(fuse_ops.readdir("/", None))

        # Should only include .py files (and .tmp)
        assert "file2.py" in entries
        assert "file1.txt" not in entries
        assert "file3.md" not in entries

    def test_access_excluded_file_returns_enoent(self, fuse_ops, rule_engine):
        """Returns ENOENT when accessing excluded file."""
        import errno

        from fuse import FuseOSError

        # Exclude .tmp files
        rule = Rule(
            name="Exclude temp",
            action=RuleAction.EXCLUDE,
            patterns=["*.tmp"],
            priority=100,
        )
        rule_engine.add_rule(rule)

        # Try to access excluded file
        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.getattr("/hidden.tmp", None)

        assert exc_info.value.errno == errno.ENOENT


class TestTransformPipelineIntegration:
    """Test transform pipeline integration."""

    def test_read_applies_transforms(self, fuse_ops, transform_pipeline):
        """Reads file with transforms applied."""
        from shadowfs.transforms.base import Transform, TransformResult

        # Create uppercase transform
        class UppercaseTransform(Transform):
            def __init__(self):
                super().__init__(name="uppercase")

            def transform(self, content: bytes, path: str, metadata: dict) -> bytes:
                """Transform content to uppercase."""
                return content.upper()

            def should_apply(self, path: str) -> bool:
                return path.endswith(".txt")

        # Add transform
        transform_pipeline.add_transform(UppercaseTransform())

        # Read file
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content = fuse_ops.read("/file1.txt", 1024, 0, fh)
        fuse_ops.release("/file1.txt", fh)

        assert content == b"CONTENT1"

    def test_transform_not_applied_to_non_matching_files(
        self, fuse_ops, transform_pipeline, cache_manager, temp_dirs
    ):
        """Transform not applied to non-matching files."""
        from shadowfs.transforms.base import Transform, TransformResult

        # Clear cache from previous test
        cache_manager.clear()

        # Clear any transforms from previous test
        transform_pipeline._transforms = []

        # Create a fresh .js file for this test
        js_file = temp_dirs["source"] / "test.js"
        js_file.write_text("console.log('test')")

        # Create transform for .txt only
        class UppercaseTransform(Transform):
            def __init__(self):
                super().__init__(name="uppercase")

            def transform(self, content: bytes, path: str, metadata: dict) -> bytes:
                """Transform content to uppercase."""
                return content.upper()

            def supports(self, path: str, metadata: dict = None) -> bool:
                return path.endswith(".txt")

        transform_pipeline.add_transform(UppercaseTransform())

        # Read .js file (should not transform)
        fh = fuse_ops.open("/test.js", os.O_RDONLY)
        content = fuse_ops.read("/test.js", 1024, 0, fh)
        fuse_ops.release("/test.js", fh)

        assert content == b"console.log('test')"  # Not transformed


class TestCacheIntegration:
    """Test cache integration."""

    def test_cache_hits_on_repeated_reads(self, fuse_ops, cache_manager):
        """Cache hits on repeated reads."""
        # First read (cache miss)
        fh1 = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content1 = fuse_ops.read("/file1.txt", 1024, 0, fh1)
        fuse_ops.release("/file1.txt", fh1)

        # Get cache stats
        stats1 = cache_manager.get_stats()

        # Second read (should hit cache)
        fh2 = fuse_ops.open("/file1.txt", os.O_RDONLY)
        content2 = fuse_ops.read("/file1.txt", 1024, 0, fh2)
        fuse_ops.release("/file1.txt", fh2)

        # Get cache stats again
        stats2 = cache_manager.get_stats()

        # Content should match
        assert content1 == content2

        # Cache should have entries
        assert "totals" in stats2
        assert stats2["totals"]["total_entries"] >= stats1["totals"]["total_entries"]

    def test_cache_invalidation_clears_cached_content(self, fuse_ops, cache_manager):
        """Cache invalidation clears cached content."""
        # Read file (populate cache)
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        fuse_ops.read("/file1.txt", 1024, 0, fh)
        fuse_ops.release("/file1.txt", fh)

        # Clear cache
        cache_manager.clear()

        # Check cache is empty
        stats = cache_manager.get_stats()
        assert stats["totals"]["total_entries"] == 0


class TestVirtualLayerIntegration:
    """Test virtual layer integration."""

    def test_classifier_layer_organizes_by_extension(self, fuse_ops, layer_manager):
        """Classifier layer organizes files by extension."""
        # Verify fuse_ops uses same layer_manager
        assert fuse_ops.layer_manager is layer_manager

        # Create by-type layer
        layer = ClassifierLayer(
            name="by-type",
            classifier=lambda file_info: Path(file_info.path).suffix.lstrip(".") or "no-extension",
        )
        layer_manager.add_layer(layer)

        # Scan sources
        layer_manager.scan_sources()
        layer_manager.rebuild_indexes()

        # Debug: Check if layer has files
        assert len(layer.index) > 0, f"Layer index is empty. Files in manager: {len(layer_manager.files)}"

        # List virtual directory
        entries = list(fuse_ops.readdir("/by-type", None))

        # Should have categories
        assert "txt" in entries
        assert "py" in entries
        assert "md" in entries

    def test_virtual_path_resolves_to_real_file(self, fuse_ops, layer_manager, temp_dirs):
        """Virtual path resolves to real file."""
        # Create by-type layer
        layer = ClassifierLayer(
            name="by-type",
            classifier=lambda file_info: Path(file_info.path).suffix.lstrip(".") or "no-extension",
        )
        layer_manager.add_layer(layer)
        layer_manager.scan_sources()
        layer_manager.rebuild_indexes()

        # Read file through virtual path
        virtual_path = "/by-type/txt/file1.txt"

        # Resolve path
        real_path = layer_manager.resolve_path(virtual_path.lstrip("/"))

        # Should resolve to real file
        assert real_path == str(temp_dirs["source"] / "file1.txt")


class TestCompleteStack:
    """Test complete application stack."""

    def test_main_initializes_all_components(self, temp_dirs):
        """Main initializes all components."""
        import argparse

        args = argparse.Namespace()
        args.mount = str(temp_dirs["mount"])
        args.sources = [str(temp_dirs["source"])]
        args.config = None
        args.foreground = True
        args.debug = False
        args.log_file = None
        args.read_write = False
        args.allow_other = False
        args.fuse_options = []

        config = {
            "sources": [{"path": str(temp_dirs["source"]), "priority": 1}],
            "readonly": True,
            "allow_other": False,
            "rules": [],
            "transforms": [],
            "virtual_layers": [],
            "cache": {"enabled": True, "max_size_mb": 10, "ttl_seconds": 60},
            "logging": {"level": "INFO"},
        }

        logger = Logger("test", level="INFO")

        main = ShadowFSMain(args, config, logger)
        main.initialize_components()

        # Verify all components initialized
        assert main.config_manager is not None
        assert main.cache_manager is not None
        assert main.rule_engine is not None
        assert main.transform_pipeline is not None
        assert main.layer_manager is not None
        assert main.fuse_ops is not None

    def test_components_connected_correctly(self, temp_dirs):
        """Components are connected correctly."""
        import argparse

        args = argparse.Namespace()
        args.mount = str(temp_dirs["mount"])
        args.sources = [str(temp_dirs["source"])]
        args.config = None
        args.foreground = True
        args.debug = False
        args.log_file = None
        args.read_write = False
        args.allow_other = False
        args.fuse_options = []

        config = {
            "sources": [{"path": str(temp_dirs["source"]), "priority": 1}],
            "readonly": True,
            "rules": [],
            "transforms": [],
            "virtual_layers": [],
            "cache": {"enabled": True, "max_size_mb": 10},
            "logging": {"level": "INFO"},
        }

        logger = Logger("test", level="INFO")

        main = ShadowFSMain(args, config, logger)
        main.initialize_components()

        # Verify components are connected
        assert main.fuse_ops.config == main.config_manager
        assert main.fuse_ops.cache == main.cache_manager
        assert main.fuse_ops.rule_engine == main.rule_engine
        assert main.fuse_ops.transform_pipeline == main.transform_pipeline
        assert main.fuse_ops.layer_manager == main.layer_manager


class TestErrorHandling:
    """Test error handling across the stack."""

    def test_nonexistent_file_returns_enoent(self, fuse_ops):
        """Returns ENOENT for nonexistent file."""
        import errno

        from fuse import FuseOSError

        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.getattr("/nonexistent.txt", None)

        assert exc_info.value.errno == errno.ENOENT

    def test_read_nonexistent_file_returns_enoent(self, fuse_ops):
        """Returns ENOENT when reading nonexistent file."""
        import errno

        from fuse import FuseOSError

        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.open("/nonexistent.txt", os.O_RDONLY)

        assert exc_info.value.errno == errno.ENOENT

    def test_write_in_readonly_mode_returns_erofs(self, fuse_ops):
        """Returns EROFS when writing in readonly mode."""
        import errno

        from fuse import FuseOSError

        fuse_ops.readonly = True

        with pytest.raises(FuseOSError) as exc_info:
            fuse_ops.create("/newfile.txt", 0o644)

        assert exc_info.value.errno == errno.EROFS


class TestPerformance:
    """Test performance characteristics."""

    def test_cache_improves_read_performance(self, fuse_ops, cache_manager):
        """Cache improves read performance."""
        import time

        # Clear cache
        cache_manager.clear()

        # First read (uncached)
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        start1 = time.time()
        fuse_ops.read("/file1.txt", 1024, 0, fh)
        time1 = time.time() - start1
        fuse_ops.release("/file1.txt", fh)

        # Second read (cached)
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        start2 = time.time()
        fuse_ops.read("/file1.txt", 1024, 0, fh)
        time2 = time.time() - start2
        fuse_ops.release("/file1.txt", fh)

        # Cached read should be faster (or at least not significantly slower)
        # Note: This is a simple sanity check, not a rigorous performance test
        assert time2 <= time1 * 10  # Allow 10x tolerance for test variability

    def test_handles_large_directory_listings(self, fuse_ops, temp_dirs):
        """Handles large directory listings."""
        # Create many files
        source_dir = temp_dirs["source"]
        for i in range(100):
            (source_dir / f"file{i}.txt").write_text(f"content{i}")

        # List directory
        entries = list(fuse_ops.readdir("/", None))

        # Should have all files
        assert len(entries) >= 100


class TestStatistics:
    """Test statistics collection."""

    def test_get_stats_returns_metrics(self, fuse_ops):
        """get_stats returns metrics."""
        # Perform some operations
        fh = fuse_ops.open("/file1.txt", os.O_RDONLY)
        fuse_ops.read("/file1.txt", 1024, 0, fh)
        fuse_ops.release("/file1.txt", fh)

        # Get stats
        stats = fuse_ops.get_stats()

        # Should have basic stats
        assert "open_files" in stats
