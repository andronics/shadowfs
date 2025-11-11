"""Shared pytest fixtures for ShadowFS tests."""
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import MagicMock

import pytest
import yaml


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def source_dir(temp_dir: Path) -> Path:
    """Create a source directory with test files."""
    source = temp_dir / "source"
    source.mkdir()

    # Create test file structure
    (source / "file.txt").write_text("Hello World")
    (source / "README.md").write_text("# Test README\n\nTest content")
    (source / "script.py").write_text("#!/usr/bin/env python\nprint('test')")

    # Create subdirectories
    (source / "subdir").mkdir()
    (source / "subdir" / "nested.txt").write_text("Nested content")

    (source / "docs").mkdir()
    (source / "docs" / "api.md").write_text("# API Documentation")

    # Create files for testing filters
    (source / ".hidden").write_text("Hidden file")
    (source / "build").mkdir()
    (source / "build" / "output.o").write_text("Binary content")

    return source


@pytest.fixture
def mount_dir(temp_dir: Path) -> Path:
    """Create a mount point directory."""
    mount = temp_dir / "mount"
    mount.mkdir()
    return mount


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide a sample ShadowFS configuration."""
    return {
        "shadowfs": {
            "version": "1.0",
            "sources": [
                {
                    "path": "/tmp/source",
                    "priority": 1,
                    "readonly": False
                }
            ],
            "rules": [
                {
                    "name": "Hide hidden files",
                    "type": "exclude",
                    "pattern": "**/.*"
                },
                {
                    "name": "Hide build artifacts",
                    "type": "exclude",
                    "patterns": [
                        "**/__pycache__/**",
                        "**/build/**",
                        "**/*.pyc"
                    ]
                }
            ],
            "transforms": [
                {
                    "name": "Markdown to HTML",
                    "pattern": "**/*.md",
                    "type": "convert",
                    "from": "markdown",
                    "to": "html"
                }
            ],
            "virtual_layers": [
                {
                    "name": "by-type",
                    "type": "classifier",
                    "classifier": "extension"
                },
                {
                    "name": "by-date",
                    "type": "date",
                    "date_field": "mtime"
                }
            ],
            "cache": {
                "enabled": True,
                "max_size_mb": 128,
                "ttl_seconds": 300
            },
            "logging": {
                "level": "DEBUG",
                "file": None
            }
        }
    }


@pytest.fixture
def config_file(temp_dir: Path, sample_config: Dict[str, Any]) -> Path:
    """Create a configuration file."""
    config_path = temp_dir / "shadowfs.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def mock_fuse():
    """Mock FUSE operations for testing."""
    mock = MagicMock()
    mock.getattr = MagicMock(return_value={"st_mode": 33188})
    mock.readdir = MagicMock(return_value=[".", "..", "file.txt"])
    mock.open = MagicMock(return_value=0)
    mock.read = MagicMock(return_value=b"content")
    return mock


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset any singleton instances between tests."""
    # Will be used when we have singleton patterns
    yield


@pytest.fixture
def benchmark_data(temp_dir: Path) -> Path:
    """Create large dataset for performance testing."""
    data_dir = temp_dir / "benchmark"
    data_dir.mkdir()

    # Create 1000 files for benchmarking
    for i in range(100):  # Reduced for initial setup
        (data_dir / f"file_{i:04d}.txt").write_text(f"Content {i}")

    # Create deep directory structure
    current = data_dir
    for i in range(5):  # Reduced depth for initial setup
        current = current / f"level_{i}"
        current.mkdir()
        (current / "data.txt").write_text(f"Level {i}")

    return data_dir