"""Phase 0 verification tests."""
import pytest
from pathlib import Path


def test_project_structure_exists():
    """Verify the project structure is created correctly."""
    root = Path(__file__).parent.parent

    # Check main package directories exist
    assert (root / "shadowfs").exists()
    assert (root / "shadowfs" / "foundation").exists()
    assert (root / "shadowfs" / "infrastructure").exists()
    assert (root / "shadowfs" / "integration").exists()
    assert (root / "shadowfs" / "application").exists()
    assert (root / "shadowfs" / "transforms").exists()

    # Check test directories exist
    assert (root / "tests").exists()
    assert (root / "tests" / "foundation").exists()
    assert (root / "tests" / "infrastructure").exists()
    assert (root / "tests" / "integration").exists()
    assert (root / "tests" / "application").exists()
    assert (root / "tests" / "e2e").exists()

    # Check configuration files exist
    assert (root / "setup.py").exists()
    assert (root / "requirements.txt").exists()
    assert (root / "requirements-dev.txt").exists()
    assert (root / "pytest.ini").exists()
    assert (root / ".flake8").exists()
    assert (root / "mypy.ini").exists()
    assert (root / "pyproject.toml").exists()
    assert (root / "Makefile").exists()

    # Check documentation files exist
    assert (root / "PLAN.md").exists()
    assert (root / "CLAUDE.md").exists()


def test_fixtures_available(temp_dir, sample_config, source_dir):
    """Verify pytest fixtures are working."""
    assert temp_dir.exists()
    assert temp_dir.is_dir()

    assert "shadowfs" in sample_config
    assert sample_config["shadowfs"]["version"] == "1.0"

    assert source_dir.exists()
    assert (source_dir / "file.txt").exists()
    assert (source_dir / "README.md").exists()


def test_python_version():
    """Verify Python version is 3.11 or higher."""
    import sys
    assert sys.version_info >= (3, 11), "Python 3.11+ required"