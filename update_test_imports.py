#!/usr/bin/env python3
"""Update imports in test files."""

import re
import sys
from pathlib import Path

MAPPINGS = [
    (r"from shadowfs\.foundation\.constants", r"from shadowfs.core.constants"),
    (r"from shadowfs\.foundation\.file_operations", r"from shadowfs.core.file_ops"),
    (r"from shadowfs\.foundation\.path_utils", r"from shadowfs.core.path_utils"),
    (r"from shadowfs\.foundation\.validators", r"from shadowfs.core.validators"),
    (r"from shadowfs\.foundation", r"from shadowfs.core"),
    (r"import shadowfs\.foundation", r"import shadowfs.core"),
    (r"shadowfs\.foundation\.", r"shadowfs.core."),
    (r"from shadowfs\.infrastructure\.cache_manager", r"from shadowfs.core.cache"),
    (r"from shadowfs\.infrastructure\.config_manager", r"from shadowfs.core.config"),
    (r"from shadowfs\.infrastructure\.logger", r"from shadowfs.core.logging"),
    (r"from shadowfs\.infrastructure\.metrics", r"from shadowfs.core.metrics"),
    (r"from shadowfs\.infrastructure", r"from shadowfs.core"),
    (r"import shadowfs\.infrastructure", r"import shadowfs.core"),
    (r"shadowfs\.infrastructure\.cache_manager", r"shadowfs.core.cache"),
    (r"shadowfs\.infrastructure\.config_manager", r"shadowfs.core.config"),
    (r"shadowfs\.infrastructure\.logger", r"shadowfs.core.logging"),
    (r"shadowfs\.infrastructure\.metrics", r"shadowfs.core.metrics"),
    (r"shadowfs\.infrastructure\.", r"shadowfs.core."),
    (r"from shadowfs\.integration\.virtual_layers", r"from shadowfs.virtual_layers"),
    (r"import shadowfs\.integration\.virtual_layers", r"import shadowfs.virtual_layers"),
    (r"shadowfs\.integration\.virtual_layers", r"shadowfs.virtual_layers"),
    (r"from shadowfs\.integration\.rule_engine", r"from shadowfs.rules.engine"),
    (r"import shadowfs\.integration\.rule_engine", r"import shadowfs.rules.engine"),
    (r"shadowfs\.integration\.rule_engine", r"shadowfs.rules.engine"),
    (r"from shadowfs\.integration\.pattern_matcher", r"from shadowfs.rules.patterns"),
    (r"import shadowfs\.integration\.pattern_matcher", r"import shadowfs.rules.patterns"),
    (r"shadowfs\.integration\.pattern_matcher", r"shadowfs.rules.patterns"),
    (r"from shadowfs\.integration\.transform_pipeline", r"from shadowfs.transforms.pipeline"),
    (r"import shadowfs\.integration\.transform_pipeline", r"import shadowfs.transforms.pipeline"),
    (r"shadowfs\.integration\.transform_pipeline", r"shadowfs.transforms.pipeline"),
    (r"from shadowfs\.application\.fuse_operations", r"from shadowfs.fuse.operations"),
    (r"from shadowfs\.application\.control_server", r"from shadowfs.fuse.control"),
    (r"from shadowfs\.application", r"from shadowfs.fuse"),
    (r"import shadowfs\.application", r"import shadowfs.fuse"),
    (r"shadowfs\.application\.", r"shadowfs.fuse."),
]


def update_file(file_path: Path):
    try:
        with open(file_path, "r") as f:
            content = f.read()

        original = content
        changes = 0

        for old, new in MAPPINGS:
            if re.search(old, content):
                content = re.sub(old, new, content)
                changes += 1

        if content != original:
            with open(file_path, "w") as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    tests_dir = Path("tests")
    updated = 0

    for py_file in tests_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        if update_file(py_file):
            print(f"Updated: {py_file}")
            updated += 1

    print(f"\nUpdated {updated} test files")


if __name__ == "__main__":
    main()
