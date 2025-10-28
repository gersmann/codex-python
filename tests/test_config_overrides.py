from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codex._binary import bundled_codex_path, resolve_target_triple
from codex.errors import CodexExecError
from codex.output_schema_file import create_output_schema_file


def test_resolve_target_triple() -> None:
    assert resolve_target_triple("linux", "x86_64") == "x86_64-unknown-linux-musl"
    assert resolve_target_triple("linux", "aarch64") == "aarch64-unknown-linux-musl"
    assert resolve_target_triple("darwin", "arm64") == "aarch64-apple-darwin"
    assert resolve_target_triple("win32", "AMD64") == "x86_64-pc-windows-msvc"


def test_resolve_target_triple_rejects_unsupported() -> None:
    with pytest.raises(CodexExecError, match="Unsupported platform"):
        resolve_target_triple("freebsd", "x86_64")


def test_bundled_codex_path_resolves_when_binary_exists() -> None:
    target = "x86_64-unknown-linux-musl"
    package_root = Path(__file__).resolve().parent.parent / "codex"
    binary_path = package_root / "vendor" / target / "codex" / "codex"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("test", encoding="utf-8")
    try:
        assert bundled_codex_path(target) == binary_path
    finally:
        if binary_path.exists():
            binary_path.unlink()
        shutil.rmtree(package_root / "vendor" / target, ignore_errors=True)


def test_bundled_codex_path_raises_when_missing() -> None:
    with pytest.raises(CodexExecError, match="Bundled codex binary not found"):
        bundled_codex_path("missing-target")


def test_output_schema_file_lifecycle() -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    output_schema = create_output_schema_file(schema)

    assert output_schema.schema_path is not None
    schema_path = Path(output_schema.schema_path)
    assert schema_path.exists()
    output_schema.cleanup()
    assert not schema_path.exists()


def test_output_schema_requires_plain_object() -> None:
    with pytest.raises(ValueError, match="plain JSON object"):
        create_output_schema_file(["not", "an", "object"])
