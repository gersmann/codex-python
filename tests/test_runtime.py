from __future__ import annotations

from pathlib import Path

import pytest

from codex import _runtime
from codex._binary import BundledCodexNotFoundError


class _ResolveError(RuntimeError):
    pass


def test_build_child_env_adds_sdk_defaults_and_overrides() -> None:
    env = _runtime.build_child_env(
        {"EXISTING": "1"},
        base_url="https://example.test",
        api_key="secret",
    )

    assert env["EXISTING"] == "1"
    assert env[_runtime.INTERNAL_ORIGINATOR_ENV] == _runtime.PYTHON_SDK_ORIGINATOR
    assert env["OPENAI_BASE_URL"] == "https://example.test"
    assert env["CODEX_API_KEY"] == "secret"


def test_build_child_env_preserves_existing_originator_override() -> None:
    env = _runtime.build_child_env(
        {_runtime.INTERNAL_ORIGINATOR_ENV: "custom-originator"},
    )

    assert env[_runtime.INTERNAL_ORIGINATOR_ENV] == "custom-originator"


def test_resolve_codex_path_prefers_explicit_path() -> None:
    resolved = _runtime.resolve_codex_path(
        "/tmp/custom-codex",
        bundled_path=lambda: Path("/tmp/bundled-codex"),
        which=lambda name: None,
        error_type=_ResolveError,
    )

    assert resolved == "/tmp/custom-codex"


def test_resolve_codex_path_falls_back_to_path_lookup() -> None:
    resolved = _runtime.resolve_codex_path(
        None,
        bundled_path=lambda: (_ for _ in ()).throw(BundledCodexNotFoundError("bundle missing")),
        which=lambda name: "/usr/bin/codex" if name == "codex" else None,
        error_type=_ResolveError,
    )

    assert resolved == "/usr/bin/codex"


def test_resolve_codex_path_raises_error_when_nothing_available() -> None:
    with pytest.raises(_ResolveError, match="Also failed to find `codex` on PATH"):
        _runtime.resolve_codex_path(
            None,
            bundled_path=lambda: (_ for _ in ()).throw(BundledCodexNotFoundError("bundle missing")),
            which=lambda name: None,
            error_type=_ResolveError,
        )


def test_resolve_codex_path_preserves_non_missing_bundle_failures() -> None:
    with pytest.raises(RuntimeError, match="permission denied"):
        _runtime.resolve_codex_path(
            None,
            bundled_path=lambda: (_ for _ in ()).throw(RuntimeError("permission denied")),
            which=lambda name: "/usr/bin/codex" if name == "codex" else None,
            error_type=_ResolveError,
        )


def test_serialize_config_overrides_flattens_nested_values() -> None:
    overrides = _runtime.serialize_config_overrides(
        {
            "model": "gpt-5",
            "features": {
                "enabled": True,
                "threshold": 1.5,
                "labels": ["a", "b"],
                "extra-settings": {},
            },
            "quoted key": {"inner value": 3},
        }
    )

    assert overrides == [
        'model="gpt-5"',
        "features.enabled=true",
        "features.threshold=1.5",
        'features.labels=["a", "b"]',
        "features.extra-settings={}",
        "quoted key.inner value=3",
    ]


def test_serialize_config_overrides_rejects_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="plain object"):
        _runtime.serialize_config_overrides([])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="cannot be null"):
        _runtime.serialize_config_overrides({"model": None})  # type: ignore[dict-item]

    with pytest.raises(ValueError, match="finite number"):
        _runtime.serialize_config_overrides({"threshold": float("inf")})
