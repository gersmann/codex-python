from __future__ import annotations

from typing import Any

import pytest

from codex import CodexConfig, CodexNativeError, run_exec, run_prompt, run_review


@pytest.fixture(autouse=True)
def clear_native(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure native functions are patched per-test to avoid requiring the extension."""
    monkeypatch.setattr("codex.exec.native_run_exec_collect", _raise_native_error)
    monkeypatch.setattr("codex.exec.native_run_review_collect", _raise_native_error)


def _raise_native_error(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - helper
    raise RuntimeError("native not patched")


def test_run_exec_passes_output_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_exec_collect(*args: Any, **kwargs: Any) -> list[dict]:
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr("codex.exec.native_run_exec_collect", fake_run_exec_collect)

    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    events = run_exec(
        "hello",
        config=CodexConfig(model="gpt-5"),
        load_default_config=False,
        output_schema=schema,
    )

    assert events == []
    assert captured["kwargs"]["output_schema"] is schema


def test_run_prompt_returns_last_message(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid native by patching run_exec to provide a minimal event stream
    from codex.event import Event

    def fake_run_exec(*args: Any, **kwargs: Any) -> list[Event]:
        return [
            Event(id="1", msg={"type": "task_started"}),
            Event(id="2", msg={"type": "task_complete", "last_agent_message": "Hello"}),
        ]

    monkeypatch.setattr("codex.exec.run_exec", fake_run_exec)

    out = run_prompt("hi", load_default_config=False)
    assert out == "Hello"


def test_run_review_forwards_user_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run_review_collect(*args: Any, **kwargs: Any) -> list[dict]:
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr("codex.exec.native_run_review_collect", fake_run_review_collect)

    events = run_review(
        "please review",
        user_facing_hint="focus files",
        config=CodexConfig(review_model="gpt-5-codex"),
        load_default_config=False,
    )

    assert events == []
    assert captured["kwargs"]["user_facing_hint"] == "focus files"
    assert captured["kwargs"]["config_overrides"]["review_model"] == "gpt-5-codex"


def test_run_review_uses_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_review_collect(*args: Any, **kwargs: Any) -> list[dict]:
        return []

    monkeypatch.setattr("codex.exec.native_run_review_collect", fake_run_review_collect)

    # Ensure defaults still flow when nothing set (no overrides / no hint)
    events = run_review("review me")
    assert isinstance(events, list)


def test_run_exec_raises_native_error_when_unpatched() -> None:
    with pytest.raises(CodexNativeError):
        run_exec("hello", load_default_config=False)


def test_run_review_raises_native_error_when_unpatched() -> None:
    with pytest.raises(CodexNativeError):
        run_review("hello", load_default_config=False)


def test_run_prompt_parses_json_when_schema_given(monkeypatch: pytest.MonkeyPatch) -> None:
    from codex.event import Event

    def fake_run_exec(*args: Any, **kwargs: Any) -> list[Event]:
        # Model wrapped the JSON in prose; we should still extract it
        text = 'Here you go:\n```json\n{\n  "answer": "42"\n}\n```'
        return [
            Event(id="2", msg={"type": "task_complete", "last_agent_message": text}),
        ]

    monkeypatch.setattr("codex.exec.run_exec", fake_run_exec)

    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    out = run_prompt("hi", load_default_config=False, output_schema=schema)
    assert out == {"answer": "42"}
