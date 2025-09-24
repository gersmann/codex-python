from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest


class _FakeNative:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    # Iterator protocol
    def __iter__(self) -> Iterator[dict[str, Any]]:  # pragma: no cover - simple passthrough
        return iter(self._events)

    # Methods the async facade will call; record invocations
    def submit_user_turn(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("submit_user_turn", args, kwargs))

    def submit_review(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("submit_review", args, kwargs))

    def approve_exec(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("approve_exec", args, kwargs))

    def approve_patch(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("approve_patch", args, kwargs))

    def interrupt(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("interrupt", args, kwargs))

    def shutdown(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("shutdown", args, kwargs))

    def user_input_text(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("user_input_text", args, kwargs))

    def override_turn_context(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("override_turn_context", args, kwargs))

    def add_to_history(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("add_to_history", args, kwargs))

    def get_history_entry(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("get_history_entry", args, kwargs))

    def get_path(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("get_path", args, kwargs))

    def list_mcp_tools(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("list_mcp_tools", args, kwargs))

    def list_custom_prompts(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("list_custom_prompts", args, kwargs))

    def compact(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("compact", args, kwargs))


def test_async_conversation_iteration_and_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        from codex import CodexClient

        # Prepare two events: session_configured then task_complete
        fake_events = [
            {
                "id": "",
                "msg": {
                    "type": "session_configured",
                    "session_id": "c",
                    "model": "gpt-5",
                    "history_log_id": 0,
                    "history_entry_count": 0,
                    "rollout_path": "/tmp/x",
                },
            },
            {"id": "2", "msg": {"type": "task_complete", "last_agent_message": "ok"}},
        ]
        native = _FakeNative(fake_events)

        def fake_start_conversation(*args: Any, **kwargs: Any) -> _FakeNative:
            return native

        # astart_conversation imports from codex.native at call time
        monkeypatch.setattr("codex.native.start_conversation", fake_start_conversation)

        client = CodexClient()
        aconv = await client.astart_conversation()

        # Issue a few calls through the async facade
        await aconv.submit_user_turn("hello")
        await aconv.user_input_text("more")
        await aconv.override_turn_context(sandbox_mode="read-only")
        await aconv.list_mcp_tools()

        # Iterate the two events
        from codex.event import Event as PyEvent

        def _etype(ev: PyEvent) -> str:
            msg = getattr(ev, "msg", None)
            root = getattr(msg, "root", None)
            if root is not None and hasattr(root, "type"):
                tval = root.type
                return tval if isinstance(tval, str) else "unknown"
            if isinstance(msg, dict):
                tval2 = msg.get("type")
                return tval2 if isinstance(tval2, str) else "unknown"
            tval3 = getattr(msg, "type", None)
            return tval3 if isinstance(tval3, str) else "unknown"

        seen: list[str] = []
        async for ev in aconv:
            seen.append(_etype(ev))

        assert seen[-1] == "task_complete"
        # Make sure at least one control call was recorded by the fake
        assert any(name == "submit_user_turn" for name, _, _ in native.calls)

    asyncio.run(_run())
