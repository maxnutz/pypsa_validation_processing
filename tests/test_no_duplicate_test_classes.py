"""Guard against silently shadowed test classes.

Python allows redefining a top-level class within the same module; the second
definition silently overwrites the first and pytest collects only the survivor,
with no warning. This test walks every module in ``tests/`` and fails if any
top-level class name is defined more than once.
"""

import ast
import collections
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent


def _duplicate_top_level_classes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    counts = collections.Counter(names)
    return sorted(name for name, count in counts.items() if count > 1)


@pytest.mark.parametrize(
    "path", sorted(TESTS_DIR.glob("test_*.py")), ids=lambda p: p.name
)
def test_no_duplicate_top_level_class_names(path: Path):
    duplicates = _duplicate_top_level_classes(path)
    assert not duplicates, (
        f"{path.name} defines the following top-level class(es) more than once, "
        f"which silently shadows earlier test methods: {duplicates}"
    )
