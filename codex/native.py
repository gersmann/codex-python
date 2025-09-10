from typing import Any, cast

try:
    from codex_native import preview_config as _preview_config
    from codex_native import run_exec_collect as _run_exec_collect
    from codex_native import start_exec_stream as _start_exec_stream
except Exception as _e:  # pragma: no cover - optional native path
    _run_exec_collect = None
    _start_exec_stream = None
    _preview_config = None


def run_exec_collect(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> list[dict]:
    """Run Codex natively (in‑process) and return a list of events as dicts.

    Requires the native extension to be built/installed (see `make dev-native`).
    Falls back to raising if the extension is not available.
    """
    if _run_exec_collect is None:
        raise RuntimeError(
            "codex_native extension not installed. Run `make dev-native` or build wheels via maturin."
        )
    return cast(list[dict], _run_exec_collect(prompt, config_overrides, load_default_config))


def start_exec_stream(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> Any:
    """Return a native streaming iterator over Codex events (dicts)."""
    if _start_exec_stream is None:
        raise RuntimeError(
            "codex_native extension not installed. Run `make dev-native` or build wheels via maturin."
        )
    return _start_exec_stream(prompt, config_overrides, load_default_config)


def preview_config(
    *, config_overrides: dict[str, Any] | None = None, load_default_config: bool = True
) -> dict:
    """Return an effective config snapshot (selected fields) from native.

    Useful for tests to validate override mapping without running Codex.
    """
    if _preview_config is None:  # pragma: no cover
        raise RuntimeError(
            "codex_native extension not installed. Run `make dev-native` or build wheels via maturin."
        )
    return cast(dict, _preview_config(config_overrides, load_default_config))
