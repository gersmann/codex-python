from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from codex._binary import BundledCodexNotFoundError, bundled_codex_path, bundled_path_dirs


def _fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    codex_path: Path | Exception,
    path_dir: Path | None = None,
) -> None:
    module = types.ModuleType("codex_cli_bin")

    def fake_codex_path() -> Path:
        if isinstance(codex_path, Exception):
            raise codex_path
        return codex_path

    module.bundled_codex_path = fake_codex_path  # type: ignore[attr-defined]
    module.bundled_path_dir = lambda: path_dir  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "codex_cli_bin", module)


def test_bundled_codex_path_comes_from_runtime_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_runtime(monkeypatch, codex_path=tmp_path / "bin" / "codex", path_dir=tmp_path / "rg")

    assert bundled_codex_path() == tmp_path / "bin" / "codex"
    assert bundled_path_dirs() == (tmp_path / "rg",)


def test_bundled_codex_path_explains_missing_runtime_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "codex_cli_bin", None)

    with pytest.raises(BundledCodexNotFoundError, match="openai-codex-cli-bin is not installed"):
        bundled_codex_path()
    assert bundled_path_dirs() == ()


def test_bundled_codex_path_reports_incomplete_runtime_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_runtime(monkeypatch, codex_path=FileNotFoundError("missing packaged codex binary"))

    with pytest.raises(BundledCodexNotFoundError, match="missing packaged codex binary"):
        bundled_codex_path()


def test_installed_runtime_ships_code_mode_host_and_sandbox() -> None:
    codex = bundled_codex_path()

    assert codex.is_file()
    assert (codex.parent / "codex-code-mode-host").is_file() or (
        codex.parent / "codex-code-mode-host.exe"
    ).is_file()
