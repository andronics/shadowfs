#!/usr/bin/env python3
"""Script to update all import statements after reorganization."""

import os
import re
from pathlib import Path

# Define import mapping (old → new)
IMPORT_MAPPINGS = [
    # Foundation → core
    (r"from shadowfs\.foundation\.constants", "from shadowfs.core.constants"),
    (r"from shadowfs\.foundation\.file_operations", "from shadowfs.core.file_ops"),
    (r"from shadowfs\.foundation\.path_utils", "from shadowfs.core.path_utils"),
    (r"from shadowfs\.foundation\.validators", "from shadowfs.core.validators"),
    (r"from shadowfs\.foundation", "from shadowfs.core"),
    (r"import shadowfs\.foundation\.constants", "import shadowfs.core.constants"),
    (r"import shadowfs\.foundation\.file_operations", "import shadowfs.core.file_ops"),
    (r"import shadowfs\.foundation\.path_utils", "import shadowfs.core.path_utils"),
    (r"import shadowfs\.foundation\.validators", "import shadowfs.core.validators"),
    (r"import shadowfs\.foundation", "import shadowfs.core"),
    # Infrastructure → core
    (r"from shadowfs\.infrastructure\.cache_manager", "from shadowfs.core.cache"),
    (r"from shadowfs\.infrastructure\.config_manager", "from shadowfs.core.config"),
    (r"from shadowfs\.infrastructure\.logger", "from shadowfs.core.logging"),
    (r"from shadowfs\.infrastructure\.metrics", "from shadowfs.core.metrics"),
    (r"from shadowfs\.infrastructure", "from shadowfs.core"),
    (r"import shadowfs\.infrastructure\.cache_manager", "import shadowfs.core.cache"),
    (r"import shadowfs\.infrastructure\.config_manager", "import shadowfs.core.config"),
    (r"import shadowfs\.infrastructure\.logger", "import shadowfs.core.logging"),
    (r"import shadowfs\.infrastructure\.metrics", "import shadowfs.core.metrics"),
    (r"import shadowfs\.infrastructure", "import shadowfs.core"),
    # Integration/virtual_layers → virtual_layers
    (r"from shadowfs\.integration\.virtual_layers\.base", "from shadowfs.virtual_layers.base"),
    (
        r"from shadowfs\.integration\.virtual_layers\.classifier_layer",
        "from shadowfs.virtual_layers.classifier",
    ),
    (
        r"from shadowfs\.integration\.virtual_layers\.date_layer",
        "from shadowfs.virtual_layers.date",
    ),
    (
        r"from shadowfs\.integration\.virtual_layers\.hierarchical_layer",
        "from shadowfs.virtual_layers.hierarchical",
    ),
    (r"from shadowfs\.integration\.virtual_layers\.tag_layer", "from shadowfs.virtual_layers.tag"),
    (
        r"from shadowfs\.integration\.virtual_layers\.manager",
        "from shadowfs.virtual_layers.manager",
    ),
    (r"from shadowfs\.integration\.virtual_layers", "from shadowfs.virtual_layers"),
    (r"import shadowfs\.integration\.virtual_layers", "import shadowfs.virtual_layers"),
    # Integration/rules → rules
    (r"from shadowfs\.integration\.rule_engine", "from shadowfs.rules.engine"),
    (r"from shadowfs\.integration\.pattern_matcher", "from shadowfs.rules.patterns"),
    (r"import shadowfs\.integration\.rule_engine", "import shadowfs.rules.engine"),
    (r"import shadowfs\.integration\.pattern_matcher", "import shadowfs.rules.patterns"),
    # Integration/transform_pipeline → transforms/pipeline
    (r"from shadowfs\.integration\.transform_pipeline", "from shadowfs.transforms.pipeline"),
    (r"import shadowfs\.integration\.transform_pipeline", "import shadowfs.transforms.pipeline"),
    # Application → fuse or top-level
    (r"from shadowfs\.application\.fuse_operations", "from shadowfs.fuse.operations"),
    (r"from shadowfs\.application\.control_server", "from shadowfs.fuse.control"),
    (r"from shadowfs\.application\.cli", "from shadowfs.cli"),
    (r"from shadowfs\.application\.shadowfs_main", "from shadowfs.main"),
    (r"import shadowfs\.application\.fuse_operations", "import shadowfs.fuse.operations"),
    (r"import shadowfs\.application\.control_server", "import shadowfs.fuse.control"),
    (r"import shadowfs\.application\.cli", "import shadowfs.cli"),
    (r"import shadowfs\.application\.shadowfs_main", "import shadowfs.main"),
]


def update_file(file_path: Path) -> tuple[int, list[str]]:
    """Update imports in a single file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        changes = []

        for old_pattern, new_pattern in IMPORT_MAPPINGS:
            if re.search(old_pattern, content):
                matches = re.findall(old_pattern, content)
                content = re.sub(old_pattern, new_pattern, content)
                for match in matches:
                    changes.append(f"  {match} → {new_pattern}")

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return (len(changes), changes)

        return (0, [])
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return (0, [])


def main():
    """Update all Python files in shadowfs directory."""
    shadowfs_dir = Path(__file__).parent / "shadowfs"

    print("Updating imports in shadowfs directory...")
    print("=" * 80)

    total_files = 0
    total_changes = 0

    for py_file in shadowfs_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        num_changes, changes = update_file(py_file)
        if num_changes > 0:
            total_files += 1
            total_changes += num_changes
            print(f"\n{py_file.relative_to(shadowfs_dir.parent)}:")
            for change in changes:
                print(change)

    print("\n" + "=" * 80)
    print(f"Updated {total_changes} imports in {total_files} files")


if __name__ == "__main__":
    main()
