from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError, URLError

import pytest


def _load_script_module(name: str, relative_path: str) -> ModuleType:
    path = Path(relative_path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load script module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_read_optional_env_returns_none_for_missing_or_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert module._read_optional_env("GITHUB_TOKEN") is None

    monkeypatch.setenv("GITHUB_TOKEN", "")
    assert module._read_optional_env("GITHUB_TOKEN") is None

    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    assert module._read_optional_env("GITHUB_TOKEN") == "secret"


def test_select_asset_for_target_prefers_exact_names() -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")
    assets = [
        module.ReleaseAsset(name="codex-x86_64-unknown-linux-gnu.tar.gz", url="tar"),
        module.ReleaseAsset(name="codex-x86_64-unknown-linux-gnu-debug.tar.gz", url="debug"),
    ]

    selected = module.select_asset_for_target(assets, "x86_64-unknown-linux-gnu")

    assert selected == module.ReleaseAsset(
        name="codex-x86_64-unknown-linux-gnu.tar.gz",
        url="tar",
    )


def test_select_asset_for_target_falls_back_to_sorted_prefix_match() -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")
    assets = [
        module.ReleaseAsset(name="codex-aarch64-apple-darwin-beta.zip", url="beta"),
        module.ReleaseAsset(name="codex-aarch64-apple-darwin-alpha.zip", url="alpha"),
    ]

    selected = module.select_asset_for_target(assets, "aarch64-apple-darwin")

    assert selected == module.ReleaseAsset(
        name="codex-aarch64-apple-darwin-alpha.zip",
        url="alpha",
    )


def test_github_json_adds_headers_and_parses_object(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            _ = (exc_type, exc, tb)

        def read(self) -> bytes:
            return b'{"assets":[]}'

    def fake_urlopen(request: object) -> _Response:
        captured["full_url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        return _Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)

    payload = module.github_json("https://example.test/releases/latest", "secret")

    assert payload == {"assets": []}
    assert captured["full_url"] == "https://example.test/releases/latest"
    headers = captured["headers"]
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["User-agent"] == module.USER_AGENT
    assert headers["Authorization"] == "Bearer secret"


def test_github_json_wraps_http_and_url_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")

    class _Body:
        def read(self) -> bytes:
            return b"failure"

        def close(self) -> None:
            return None

    def raise_http_error(request: object) -> object:
        _ = request
        raise HTTPError("https://example.test", 500, "boom", hdrs=None, fp=_Body())

    monkeypatch.setattr(module, "urlopen", raise_http_error)

    with pytest.raises(RuntimeError, match="GitHub API request failed \\(500\\)"):
        module.github_json("https://example.test", None)

    def raise_url_error(request: object) -> object:
        _ = request
        raise URLError("offline")

    monkeypatch.setattr(module, "urlopen", raise_url_error)

    with pytest.raises(RuntimeError, match="Network error while requesting"):
        module.github_json("https://example.test", None)


def test_fetch_helpers_reject_non_https_urls() -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")

    with pytest.raises(RuntimeError, match="non-HTTPS"):
        module.github_json("http://example.test/releases/latest", None)

    with pytest.raises(RuntimeError, match="non-HTTPS"):
        module.download("file:///tmp/example.tar.gz", Path("/tmp/out"), None)


def test_extract_zst_uses_timeout_for_cli_decoder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module("fetch_codex_binary", "scripts/fetch_codex_binary.py")
    archive_path = tmp_path / "codex.zst"
    archive_path.write_bytes(b"compressed")
    destination = tmp_path / "codex"
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        module.shutil, "which", lambda name: "/usr/bin/zstd" if name == "zstd" else None
    )

    def fake_run(command: list[str], *, check: bool, timeout: int) -> None:
        captured["command"] = command
        captured["check"] = check
        captured["timeout"] = timeout

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._extract_zst(archive_path, destination)

    assert captured == {
        "command": ["/usr/bin/zstd", "-f", "-d", str(archive_path), "-o", str(destination)],
        "check": True,
        "timeout": module.ZSTD_TIMEOUT_SECONDS,
    }
