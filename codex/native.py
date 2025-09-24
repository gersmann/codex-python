from typing import Any, cast

from codex_native import NativeConversation as _NativeConversation
from codex_native import preview_config as _preview_config
from codex_native import run_exec_collect as _run_exec_collect
from codex_native import run_review_collect as _run_review_collect
from codex_native import start_conversation as _start_conversation
from codex_native import start_exec_stream as _start_exec_stream
from codex_native import start_review_stream as _start_review_stream


def run_exec_collect(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
    output_schema: Any | None = None,
) -> list[dict]:
    """Run Codex natively (in‑process) and return a list of events as dicts."""
    return cast(
        list[dict],
        _run_exec_collect(prompt, config_overrides, load_default_config, output_schema),
    )


def start_exec_stream(
    prompt: str,
    *,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
    output_schema: Any | None = None,
) -> Any:
    """Return a native streaming iterator over Codex events (dicts)."""
    return _start_exec_stream(prompt, config_overrides, load_default_config, output_schema)


def run_review_collect(
    prompt: str,
    *,
    user_facing_hint: str | None = None,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> list[dict]:
    """Run Codex review mode and return captured events as dicts."""
    return cast(
        list[dict],
        _run_review_collect(prompt, user_facing_hint, config_overrides, load_default_config),
    )


def start_review_stream(
    prompt: str,
    *,
    user_facing_hint: str | None = None,
    config_overrides: dict[str, Any] | None = None,
    load_default_config: bool = True,
) -> Any:
    """Return a streaming iterator over review-mode events."""
    return _start_review_stream(prompt, user_facing_hint, config_overrides, load_default_config)


def preview_config(
    *, config_overrides: dict[str, Any] | None = None, load_default_config: bool = True
) -> dict:
    """Return an effective config snapshot (selected fields) from native.

    Useful for tests to validate override mapping without running Codex.
    """
    return cast(dict, _preview_config(config_overrides, load_default_config))


def start_conversation(
    *, config_overrides: dict[str, Any] | None = None, load_default_config: bool = True
) -> _NativeConversation:
    """Create a native conversation and return the native handle.

    The returned object is an iterator of event dicts and exposes methods:
    - submit_user_turn(prompt, ..., output_schema=None)
    - submit_review(prompt, user_facing_hint=None)
    - approve_exec(id, decision)
    - approve_patch(id, decision)
    - interrupt()
    - shutdown()
    """
    return _start_conversation(config_overrides, load_default_config)
