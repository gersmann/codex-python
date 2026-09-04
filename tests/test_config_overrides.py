from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from codex import _binary
from codex._binary import bundled_app_server_path, resolve_target_triple
from codex.errors import CodexExecError
from codex.output_schema_file import create_output_schema_file


class AnswerSchema(BaseModel):
    answer: str


def test_resolve_target_triple() -> None:
    assert resolve_target_triple("linux", "x86_64") == "x86_64-unknown-linux-musl"
    assert resolve_target_triple("linux", "aarch64") == "aarch64-unknown-linux-musl"
    assert resolve_target_triple("darwin", "arm64") == "aarch64-apple-darwin"
    assert resolve_target_triple("win32", "AMD64") == "x86_64-pc-windows-msvc"


def test_resolve_target_triple_rejects_unsupported() -> None:
    with pytest.raises(CodexExecError, match="Unsupported platform"):
        resolve_target_triple("freebsd", "x86_64")


def test_bundled_app_server_path_resolves_when_binary_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = "x86_64-unknown-linux-musl"
    package_root = tmp_path / "codex"
    monkeypatch.setattr(_binary, "__file__", str(package_root / "_binary.py"))
    binary_path = package_root / "vendor" / target / "codex-app-server" / "codex-app-server"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("test", encoding="utf-8")

    assert bundled_app_server_path(target) == binary_path


def test_bundled_app_server_path_raises_when_missing() -> None:
    with pytest.raises(CodexExecError, match="Bundled codex app-server binary not found"):
        bundled_app_server_path("missing-target")


def test_output_schema_file_lifecycle() -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    output_schema = create_output_schema_file(schema)

    assert output_schema.schema_path is not None
    schema_path = Path(output_schema.schema_path)
    assert schema_path.exists()
    output_schema.cleanup()
    assert not schema_path.exists()


def test_output_schema_file_accepts_pydantic_model_class() -> None:
    output_schema = create_output_schema_file(AnswerSchema)

    assert output_schema.schema_path is not None
    schema_path = Path(output_schema.schema_path)
    assert schema_path.exists()
    assert schema_path.read_text(encoding="utf-8")
    output_schema.cleanup()
    assert not schema_path.exists()


def test_output_schema_requires_json_object_or_pydantic_model_class() -> None:
    with pytest.raises(ValueError, match="JSON object or a Pydantic model class"):
        create_output_schema_file(["not", "an", "object"])
