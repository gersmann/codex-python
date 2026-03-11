from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_pin_supported_major_ranges() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    dependencies = pyproject["project"]["dependencies"]
    websocket_dependencies = pyproject["project"]["optional-dependencies"]["websocket"]

    assert "pydantic>=2.11.7,<3" in dependencies
    assert "websockets>=15.0.1,<16" in websocket_dependencies
