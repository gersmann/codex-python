from __future__ import annotations

import py_compile
from pathlib import Path


def test_examples_compile() -> None:
    for example_path in Path("examples").glob("*.py"):
        py_compile.compile(str(example_path), doraise=True)
