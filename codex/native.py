from typing import Any, cast

from codex_native import preview_config as _preview_config
from codex_native import run_exec_collect as _run_exec_collect
from codex_native import start_exec_stream as _start_exec_stream


def run_exec_collect(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> list[dict]:
    """Run Codex natively (in‑process) and return a list of events as dicts."""
    return cast(list[dict], _run_exec_collect(prompt, config_overrides, load_default_config))


def start_exec_stream(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> Any:
    """Return a native streaming iterator over Codex events (dicts)."""
    return _start_exec_stream(prompt, config_overrides, load_default_config)


def preview_config(
    *, config_overrides: dict[str, Any] | None = None, load_default_config: bool = True
) -> dict:
    """Return an effective config snapshot (selected fields) from native.

    Useful for tests to validate override mapping without running Codex.
    """
    return cast(dict, _preview_config(config_overrides, load_default_config))
