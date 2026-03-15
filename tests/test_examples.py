from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

import examples.app_server_conversation as app_server_conversation
import examples.app_server_dynamic_tool as app_server_dynamic_tool
import examples.app_server_stream_events as app_server_stream_events
import examples.app_server_tool_handler as app_server_tool_handler
import examples.app_server_websocket_conversation as app_server_websocket_conversation
import examples.basic_conversation as basic_conversation
from codex.protocol import types as protocol


class _FakeStream:
    def __init__(self, final_text: str, events: list[object] | None = None) -> None:
        self.final_text = final_text
        self.text_deltas = tuple(
            event.params.delta
            for event in (events or [])
            if isinstance(event, protocol.ItemAgentMessageDeltaNotification)
        )
        self._events = list(events or [])
        self.wait_calls = 0

    def __iter__(self) -> Iterator[object]:
        return iter(self._events)

    def wait(self) -> _FakeStream:
        self.wait_calls += 1
        return self


class _FakeThread:
    def __init__(self, stream: _FakeStream) -> None:
        self._stream = stream
        self.run_calls: list[str] = []
        self.run_text_calls: list[str] = []

    def run(self, prompt: str) -> _FakeStream:
        self.run_calls.append(prompt)
        return self._stream

    def run_text(self, prompt: str) -> str:
        self.run_text_calls.append(prompt)
        return self._stream.final_text


class _FakeClient:
    def __init__(self, thread: _FakeThread) -> None:
        self._thread = thread
        self.on_request_calls: list[tuple[str, object, object | None]] = []
        self.run_text_calls: list[str] = []
        self.start_thread_calls: list[object | None] = []

    def start_thread(self, options: object | None = None) -> _FakeThread:
        self.start_thread_calls.append(options)
        return self._thread

    def run_text(self, prompt: str) -> str:
        self.run_text_calls.append(prompt)
        return self._thread.run_text(prompt)

    def on_request(
        self, method: str, handler: object, *, request_model: object | None = None
    ) -> None:
        self.on_request_calls.append((method, handler, request_model))


@contextmanager
def _client_context(fake_client: _FakeClient) -> Iterator[_FakeClient]:
    yield fake_client


def _delta_event(delta: str) -> protocol.ItemAgentMessageDeltaNotification:
    return protocol.ItemAgentMessageDeltaNotification.model_validate(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "itemId": "item-1",
                "delta": delta,
            },
        }
    )


def test_app_server_conversation_main_prints_final_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stream = _FakeStream("Repository summary")
    fake_client = _FakeClient(_FakeThread(stream))

    monkeypatch.setattr(
        app_server_conversation.AppServerClient,
        "connect_stdio",
        classmethod(lambda cls, initialize_options=None: _client_context(fake_client)),
    )

    app_server_conversation.main()

    assert stream.wait_calls == 1
    assert capsys.readouterr().out == "Repository summary\n"


def test_app_server_stream_events_main_streams_deltas(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stream = _FakeStream(
        "Repository summary",
        events=[_delta_event("Repository "), _delta_event("summary")],
    )
    fake_client = _FakeClient(_FakeThread(stream))

    monkeypatch.setattr(
        app_server_stream_events.AppServerClient,
        "connect_stdio",
        classmethod(lambda cls, initialize_options=None: _client_context(fake_client)),
    )

    app_server_stream_events.main()

    assert capsys.readouterr().out == "Repository summary\n"


def test_app_server_tool_handler_registers_handler_and_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_client = _FakeClient(_FakeThread(_FakeStream("Handled response")))

    monkeypatch.setattr(
        app_server_tool_handler.AppServerClient,
        "connect_stdio",
        classmethod(lambda cls, initialize_options=None: _client_context(fake_client)),
    )

    app_server_tool_handler.main()

    assert fake_client.on_request_calls == [
        ("item/tool/call", app_server_tool_handler.handle_tool_call, protocol.ItemToolCallRequest)
    ]
    assert capsys.readouterr().out == "Handled response\n"


def test_app_server_dynamic_tool_registers_tool_and_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_client = _FakeClient(_FakeThread(_FakeStream("Ticket summary")))

    monkeypatch.setattr(
        app_server_dynamic_tool.AppServerClient,
        "connect_stdio",
        classmethod(lambda cls, initialize_options=None: _client_context(fake_client)),
    )

    app_server_dynamic_tool.main()

    assert fake_client.on_request_calls == [
        ("item/tool/call", app_server_dynamic_tool.handle_tool_call, protocol.ItemToolCallRequest)
    ]
    start_options = fake_client.start_thread_calls[-1]
    assert start_options is not None
    assert len(start_options.dynamic_tools) == 1
    dynamic_tool = start_options.dynamic_tools[0]
    assert dynamic_tool.name == "lookup_ticket"
    assert dynamic_tool.description == "Look up a support ticket by id."
    assert dynamic_tool.inputSchema == {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
    }
    assert capsys.readouterr().out == "Ticket summary\n"


def test_app_server_websocket_conversation_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_APP_SERVER_WEBSOCKET_URL", raising=False)

    with pytest.raises(RuntimeError, match="Set CODEX_APP_SERVER_WEBSOCKET_URL"):
        app_server_websocket_conversation._require_env("CODEX_APP_SERVER_WEBSOCKET_URL")


def test_app_server_websocket_conversation_main_uses_websocket_options(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}
    fake_client = _FakeClient(_FakeThread(_FakeStream("Websocket summary")))

    def fake_connect_websocket(
        cls: type[object],
        url: str,
        *,
        websocket_options: object = None,
        initialize_options: object = None,
    ) -> object:
        _ = cls
        captured["url"] = url
        captured["websocket_options"] = websocket_options
        captured["initialize_options"] = initialize_options
        return _client_context(fake_client)

    monkeypatch.setattr(
        app_server_websocket_conversation.AppServerClient,
        "connect_websocket",
        classmethod(fake_connect_websocket),
    )
    monkeypatch.setenv("CODEX_APP_SERVER_WEBSOCKET_URL", "ws://127.0.0.1:4500")
    monkeypatch.setenv("CODEX_APP_SERVER_BEARER_TOKEN", "secret-token")

    app_server_websocket_conversation.main()

    assert captured["url"] == "ws://127.0.0.1:4500"
    websocket_options = captured["websocket_options"]
    assert websocket_options is not None
    assert websocket_options.bearer_token == "secret-token"
    assert websocket_options.open_timeout == 10
    assert websocket_options.close_timeout == 10
    assert capsys.readouterr().out == "Websocket summary\n"


def test_basic_conversation_main_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_thread = _FakeThread(_FakeStream("Basic summary"))
    fake_codex = _FakeClient(fake_thread)

    monkeypatch.setattr(
        basic_conversation,
        "Codex",
        lambda: fake_codex,
    )

    basic_conversation.main()

    assert fake_codex.run_text_calls == ["Briefly summarize this repository's purpose."]
    assert fake_thread.run_text_calls == ["Briefly summarize this repository's purpose."]
    assert capsys.readouterr().out == "Basic summary\n"
