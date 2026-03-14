from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from pathlib import Path

from codex._binary import BundledCodexNotFoundError
from codex._config_types import CodexConfigObject, CodexConfigValue

INTERNAL_ORIGINATOR_ENV = "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
PYTHON_SDK_ORIGINATOR = "codex_sdk_py"
TOML_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def build_child_env(
    env_override: Mapping[str, str] | None,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    env = {} if env_override is None else dict(env_override)
    if INTERNAL_ORIGINATOR_ENV not in env:
        env[INTERNAL_ORIGINATOR_ENV] = PYTHON_SDK_ORIGINATOR
    if base_url is not None:
        env["OPENAI_BASE_URL"] = base_url
    if api_key is not None:
        env["CODEX_API_KEY"] = api_key
    return env


def resolve_codex_path(
    executable_path: str | None,
    *,
    bundled_path: Callable[[], Path],
    which: Callable[[str], str | None],
    error_type: type[Exception],
) -> str:
    if executable_path is not None:
        return str(Path(executable_path))
    try:
        return str(bundled_path())
    except BundledCodexNotFoundError as bundled_error:
        system_codex = which("codex")
        if system_codex is None:
            raise error_type(
                f"{bundled_error} Also failed to find `codex` on PATH."
            ) from bundled_error
        return system_codex


def serialize_config_overrides(config_overrides: CodexConfigObject) -> list[str]:
    overrides: list[str] = []
    _flatten_config_overrides(config_overrides, "", overrides)
    return overrides


def _flatten_config_overrides(
    value: CodexConfigValue | CodexConfigObject,
    prefix: str,
    overrides: list[str],
) -> None:
    if not isinstance(value, dict):
        if prefix == "":
            raise ValueError("Codex config overrides must be a plain object")
        overrides.append(f"{prefix}={_to_toml_value(value, prefix)}")
        return

    entries = list(value.items())
    if prefix == "" and not entries:
        return
    if prefix != "" and not entries:
        overrides.append(f"{prefix}={{}}")
        return

    for key, child in entries:
        if not isinstance(key, str) or key == "":
            raise ValueError("Codex config override keys must be non-empty strings")
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            _flatten_config_overrides(child, path, overrides)
        else:
            overrides.append(f"{path}={_to_toml_value(child, path)}")


def _to_toml_value(value: CodexConfigValue, path: str) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return format_toml_bool(value)
    if isinstance(value, int):
        return f"{value}"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Codex config override at {path} must be a finite number")
        return f"{value}"
    if isinstance(value, list):
        rendered_items = [
            _to_toml_value(item, f"{path}[{index}]") for index, item in enumerate(value)
        ]
        return f"[{', '.join(rendered_items)}]"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, child in value.items():
            if not isinstance(key, str) or key == "":
                raise ValueError("Codex config override keys must be non-empty strings")
            parts.append(f"{format_toml_key(key)} = {_to_toml_value(child, f'{path}.{key}')}")
        return f"{{{', '.join(parts)}}}"
    if value is None:
        raise ValueError(f"Codex config override at {path} cannot be null")
    raise ValueError(f"Unsupported Codex config override value at {path}: {type(value).__name__}")


def format_toml_key(key: str) -> str:
    if TOML_BARE_KEY.match(key):
        return key
    return json.dumps(key)


def format_toml_bool(value: bool) -> str:
    return "true" if value else "false"
