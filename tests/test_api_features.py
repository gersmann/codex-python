from __future__ import annotations

import threading
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from codex import (
    Codex,
    CodexOptions,
    ThreadResumeOptions,
    ThreadStartOptions,
    TurnOptions,
    dynamic_tool,
)
from codex.app_server import (
    AppServerClient,
    AppServerProcessOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnError,
    AppServerTurnOptions,
)
from codex.errors import ThreadRunError
from codex.protocol import types as protocol

JsonObject = dict[str, Any]


class SummaryModel(BaseModel):
    answer: str


def _thread_payload(thread_id: str = "thr-1") -> JsonObject:
    return {
        "id": thread_id,
        "preview": "",
        "ephemeral": False,
        "modelProvider": "openai",
        "createdAt": 1730910000,
        "updatedAt": 1730910000,
        "cwd": "/repo",
        "cliVersion": "1.0.0",
        "source": "appServer",
        "status": {"type": "idle"},
        "turns": [],
    }


def _turn_payload(turn_id: str = "turn-1", *, status: str = "inProgress") -> JsonObject:
    return {
        "id": turn_id,
        "status": status,
        "items": [],
        "error": None,
    }


def _agent_message_item(text: str, item_id: str = "item-1") -> JsonObject:
    return {
        "id": item_id,
        "type": "agentMessage",
        "phase": "final_answer",
        "text": text,
    }


def _turn_started_notification(thread_id: str = "thr-1", turn_id: str = "turn-1") -> BaseModel:
    return protocol.TurnStartedNotificationModel.model_validate(
        {
            "method": "turn/started",
            "params": {
                "threadId": thread_id,
                "turn": _turn_payload(turn_id),
            },
        }
    )


def _message_delta_notification(
    text: str,
    *,
    thread_id: str = "thr-1",
    turn_id: str = "turn-1",
    item_id: str = "item-1",
) -> BaseModel:
    return protocol.ItemAgentMessageDeltaNotification.model_validate(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "itemId": item_id,
                "delta": text,
            },
        }
    )


def _item_completed_notification(
    text: str,
    *,
    thread_id: str = "thr-1",
    turn_id: str = "turn-1",
    item_id: str = "item-1",
) -> BaseModel:
    return protocol.ItemCompletedNotificationModel.model_validate(
        {
            "method": "item/completed",
            "params": {
                "threadId": thread_id,
                "turnId": turn_id,
                "item": _agent_message_item(text, item_id=item_id),
            },
        }
    )


def _usage_notification(
    *,
    thread_id: str = "thr-1",
    input_tokens: int = 42,
    cached_input_tokens: int = 12,
    output_tokens: int = 5,
) -> BaseModel:
    total_tokens = input_tokens + cached_input_tokens + output_tokens
    return protocol.ThreadTokenUsageUpdatedNotificationModel.model_validate(
        {
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": thread_id,
                "turnId": "turn-1",
                "tokenUsage": {
                    "last": {
                        "inputTokens": input_tokens,
                        "cachedInputTokens": cached_input_tokens,
                        "outputTokens": output_tokens,
                        "reasoningOutputTokens": 0,
                        "totalTokens": total_tokens,
                    },
                    "total": {
                        "inputTokens": input_tokens,
                        "cachedInputTokens": cached_input_tokens,
                        "outputTokens": output_tokens,
                        "reasoningOutputTokens": 0,
                        "totalTokens": total_tokens,
                    },
                },
            },
        }
    )


def _turn_completed_notification(
    *,
    thread_id: str = "thr-1",
    turn_id: str = "turn-1",
    status: str = "completed",
    error_message: str | None = None,
) -> BaseModel:
    payload = _turn_payload(turn_id, status=status)
    if error_message is not None:
        payload["error"] = {
            "message": error_message,
            "codexErrorInfo": None,
            "additionalDetails": None,
        }
    return protocol.TurnCompletedNotificationModel.model_validate(
        {
            "method": "turn/completed",
            "params": {
                "threadId": thread_id,
                "turn": payload,
            },
        }
    )


class _FakeAppTurnStream:
    def __init__(self, notifications: Sequence[BaseModel]) -> None:
        self._notifications = list(notifications)
        self._index = 0
        self.initial_turn = protocol.Turn.model_validate(_turn_payload())
        self.final_turn: protocol.Turn | None = None
        self.final_text = ""
        self.final_message: protocol.AgentMessageThreadItem | None = None
        self.items: list[protocol.ThreadItem] = []
        self.usage: protocol.ThreadTokenUsage | None = None
        self._item_index: dict[str, int] = {}
        self._text_deltas: list[str] = []
        self.closed = False
        self.interrupt_calls = 0

    def __iter__(self) -> _FakeAppTurnStream:
        return self

    def __next__(self) -> BaseModel:
        if self._index >= len(self._notifications):
            raise StopIteration
        notification = self._notifications[self._index]
        self._index += 1
        self._apply(notification)
        return notification

    @property
    def text_deltas(self) -> tuple[str, ...]:
        return tuple(self._text_deltas)

    def wait(self) -> _FakeAppTurnStream:
        for _ in self:
            pass
        return self

    def close(self) -> None:
        self.closed = True

    def interrupt(self) -> None:
        self.interrupt_calls += 1

    def final_json(self) -> object:
        import json

        if self.final_message is None:
            raise ValueError(
                "No final message is available yet. Wait for the turn stream to complete."
            )
        return json.loads(self.final_message.text)

    def final_model(self, model_type: type[SummaryModel]) -> SummaryModel:
        if self.final_message is None:
            raise ValueError(
                "No final message is available yet. Wait for the turn stream to complete."
            )
        return model_type.model_validate_json(self.final_message.text)

    def raise_for_terminal_status(self) -> None:
        if self.final_turn is None:
            return
        if self.final_turn.status.root == "failed":
            message = "Turn failed"
            if self.final_turn.error is not None:
                message = self.final_turn.error.message
            raise AppServerTurnError(message, turn=self.final_turn)
        if self.final_turn.status.root == "interrupted":
            raise AppServerTurnError("Turn aborted: interrupted", turn=self.final_turn)

    def _apply(self, notification: BaseModel) -> None:
        if isinstance(notification, protocol.ItemAgentMessageDeltaNotification):
            self._text_deltas.append(notification.params.delta)
            self.final_text += notification.params.delta
            return
        if isinstance(notification, protocol.ThreadTokenUsageUpdatedNotificationModel):
            self.usage = notification.params.tokenUsage
            return
        if isinstance(notification, protocol.ItemCompletedNotificationModel):
            item = notification.params.item
            item_id = item.root.id
            if item_id in self._item_index:
                self.items[self._item_index[item_id]] = item
            else:
                self._item_index[item_id] = len(self.items)
                self.items.append(item)
            if isinstance(item.root, protocol.AgentMessageThreadItem):
                self.final_message = item.root
                self.final_text = item.root.text
            return
        if isinstance(notification, protocol.TurnCompletedNotificationModel):
            self.final_turn = notification.params.turn


class _InterruptibleFakeTurnStream(_FakeAppTurnStream):
    def __init__(self) -> None:
        super().__init__([])
        self._interrupted = threading.Event()
        self._completed = False

    def __next__(self) -> BaseModel:
        if self._completed:
            raise StopIteration
        if not self._interrupted.wait(timeout=1):
            raise AssertionError("expected interrupt request")
        self._completed = True
        notification = _turn_completed_notification(status="interrupted")
        self._apply(notification)
        return notification

    def interrupt(self) -> None:
        super().interrupt()
        self._interrupted.set()


class _FakeAppThread:
    def __init__(self, thread_id: str, streams: Sequence[_FakeAppTurnStream]) -> None:
        self.id = thread_id
        self._streams = list(streams)
        self.run_calls: list[tuple[object, AppServerTurnOptions | None]] = []

    def run(self, input: object, options: AppServerTurnOptions | None = None) -> _FakeAppTurnStream:
        self.run_calls.append((input, options))
        if not self._streams:
            raise AssertionError("unexpected extra run")
        return self._streams.pop(0)


class _FakeAccountClient:
    def __init__(self) -> None:
        self.login_api_key_calls: list[str] = []

    def login_api_key(self, *, api_key: str) -> object:
        self.login_api_key_calls.append(api_key)
        return object()


class _FakeAppServerClient:
    def __init__(
        self,
        start_thread: _FakeAppThread | Sequence[_FakeAppThread],
        resume_thread: _FakeAppThread | None = None,
    ) -> None:
        if isinstance(start_thread, Sequence):
            self._start_threads = list(start_thread)
            if not self._start_threads:
                raise ValueError("start_thread sequence must be non-empty")
            self._default_start_thread = self._start_threads[-1]
        else:
            self._start_threads = []
            self._default_start_thread = start_thread
        self._resume_thread = resume_thread or self._default_start_thread
        self.start_calls: list[tuple[object | None, object | None]] = []
        self.resume_calls: list[tuple[str, object]] = []
        self.closed = False
        self.account = _FakeAccountClient()

    def start_thread(
        self,
        options: object | None = None,
        *,
        tools: object | None = None,
    ) -> _FakeAppThread:
        self.start_calls.append((options, tools))
        if self._start_threads:
            return self._start_threads.pop(0)
        return self._default_start_thread

    def resume_thread(self, thread_id: str, options: object | None = None) -> _FakeAppThread:
        self.resume_calls.append((thread_id, options))
        return self._resume_thread

    def close(self) -> None:
        self.closed = True


def _patch_connect_stdio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_client: _FakeAppServerClient,
    capture: dict[str, object],
) -> None:
    def fake_connect_stdio(
        cls: type[AppServerClient],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeAppServerClient:
        _ = cls
        capture["connect_calls"] = int(capture.get("connect_calls", 0)) + 1
        capture["process_options"] = process_options
        capture["initialize_options"] = initialize_options
        return fake_client

    monkeypatch.setattr(AppServerClient, "connect_stdio", classmethod(fake_connect_stdio))


def test_run_returns_protocol_notifications_and_aggregates_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifications = [
        _turn_started_notification(),
        _message_delta_notification("Repo "),
        _message_delta_notification("summary"),
        _usage_notification(),
        _item_completed_notification("Repo summary"),
        _turn_completed_notification(),
    ]
    fake_thread = _FakeAppThread("thr-1", [_FakeAppTurnStream(notifications)])
    fake_client = _FakeAppServerClient(fake_thread)
    capture: dict[str, object] = {}
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture=capture)

    client = Codex()
    thread = client.start_thread()

    assert thread.id == "thr-1"

    stream = thread.run("hello")
    events = list(stream)

    assert [type(event) for event in events] == [
        protocol.TurnStartedNotificationModel,
        protocol.ItemAgentMessageDeltaNotification,
        protocol.ItemAgentMessageDeltaNotification,
        protocol.ThreadTokenUsageUpdatedNotificationModel,
        protocol.ItemCompletedNotificationModel,
        protocol.TurnCompletedNotificationModel,
    ]
    assert thread.id == "thr-1"
    assert stream.turn_id == "turn-1"
    assert stream.thread_id == "thr-1"
    assert stream.final_text == "Repo summary"
    assert stream.text_deltas == ("Repo ", "summary")
    assert len(stream.items) == 1
    assert stream.usage is not None
    assert stream.usage.last.inputTokens == 42
    assert isinstance(fake_thread.run_calls[0][1], AppServerTurnOptions)
    assert capture["process_options"] == AppServerProcessOptions()


def test_codex_run_text_uses_ephemeral_thread_per_call(monkeypatch: pytest.MonkeyPatch) -> None:
    first_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_item_completed_notification("First"), _turn_completed_notification()]
            )
        ],
    )
    second_thread = _FakeAppThread(
        "thr-2",
        [
            _FakeAppTurnStream(
                [
                    _item_completed_notification("Second"),
                    _turn_completed_notification(thread_id="thr-2"),
                ]
            )
        ],
    )
    fake_client = _FakeAppServerClient([first_thread, second_thread])
    capture: dict[str, object] = {}
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture=capture)

    client = Codex()

    assert client.run_text("first input") == "First"
    assert client.run_text("second input") == "Second"
    assert capture["connect_calls"] == 1
    assert len(fake_client.start_calls) == 2
    assert first_thread.run_calls[0][0] == "first input"
    assert second_thread.run_calls[0][0] == "second input"


def test_codex_run_passes_thread_options_through(monkeypatch: pytest.MonkeyPatch) -> None:
    notifications = [
        _turn_started_notification(thread_id="thr-run"),
        _item_completed_notification("Repo summary", thread_id="thr-run"),
        _turn_completed_notification(thread_id="thr-run"),
    ]
    fake_thread = _FakeAppThread("thr-run", [_FakeAppTurnStream(notifications)])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread_options = ThreadStartOptions(model="gpt-5", cwd="/tmp/project")
    turn_options = TurnOptions(model="gpt-5-mini")

    stream = client.run("hello", turn_options, thread_options=thread_options)

    assert list(stream)[-1] == notifications[-1]
    assert stream.thread_id == "thr-run"
    assert fake_client.start_calls == [(thread_options.to_app_server_options(), None)]
    assert fake_thread.run_calls[0][1] == turn_options.to_app_server_options()


def test_codex_run_accepts_app_server_option_types(monkeypatch: pytest.MonkeyPatch) -> None:
    notifications = [
        _turn_started_notification(thread_id="thr-run"),
        _item_completed_notification("Repo summary", thread_id="thr-run"),
        _turn_completed_notification(thread_id="thr-run"),
    ]
    fake_thread = _FakeAppThread("thr-run", [_FakeAppTurnStream(notifications)])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread_options = AppServerThreadStartOptions(model="gpt-5", cwd="/tmp/project")
    turn_options = AppServerTurnOptions(model="gpt-5-mini")

    stream = client.run("hello", turn_options, thread_options=thread_options)

    assert stream.thread_id == "thr-run"
    assert fake_client.start_calls == [(thread_options, None)]
    assert fake_thread.run_calls[0][1] == turn_options


def test_codex_run_passes_annotation_driven_tools_through(monkeypatch: pytest.MonkeyPatch) -> None:
    notifications = [
        _turn_started_notification(thread_id="thr-run"),
        _item_completed_notification("Repo summary", thread_id="thr-run"),
        _turn_completed_notification(thread_id="thr-run"),
    ]
    fake_thread = _FakeAppThread("thr-run", [_FakeAppTurnStream(notifications)])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    @dynamic_tool
    def lookup_ticket(id: str) -> str:
        """Look up a support ticket by id."""
        return id

    stream = Codex().run("hello", tools=[lookup_ticket])

    assert stream.thread_id == "thr-run"
    assert fake_client.start_calls == [
        (ThreadStartOptions().to_app_server_options(), [lookup_ticket])
    ]


def test_run_preserves_usage_when_turn_completed_omits_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifications = [
        _usage_notification(input_tokens=17, cached_input_tokens=3, output_tokens=9),
        _turn_completed_notification(),
    ]
    fake_thread = _FakeAppThread("thr-1", [_FakeAppTurnStream(notifications)])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    stream = Codex().start_thread().run("hello")
    stream.wait()

    assert stream.usage is not None
    assert stream.usage.last.inputTokens == 17
    assert stream.usage.last.cachedInputTokens == 3
    assert stream.usage.last.outputTokens == 9


def test_run_text_twice_reuses_materialized_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [
                    _item_completed_notification("First"),
                    _turn_completed_notification(),
                ]
            ),
            _FakeAppTurnStream(
                [
                    _item_completed_notification("Second"),
                    _turn_completed_notification(),
                ]
            ),
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread = client.start_thread()

    assert thread.run_text("first input") == "First"
    assert thread.run_text("second input") == "Second"
    assert len(fake_client.start_calls) == 1
    assert len(fake_thread.run_calls) == 2


def test_resume_thread_uses_supplied_thread_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_thread = _FakeAppThread(
        "thread-1",
        [
            _FakeAppTurnStream(
                [
                    _item_completed_notification("Resumed", thread_id="thread-1"),
                    _turn_completed_notification(thread_id="thread-1"),
                ]
            )
        ],
    )
    fake_client = _FakeAppServerClient(start_thread=fake_thread, resume_thread=fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    resume_options = ThreadResumeOptions(cwd="/tmp/project")
    thread = client.resume_thread("thread-1", resume_options)

    assert thread.id == "thread-1"
    assert thread.run_text("continue") == "Resumed"
    assert fake_client.resume_calls[0][0] == "thread-1"
    assert fake_client.resume_calls[0][1] == resume_options.to_app_server_options()


def test_resume_thread_accepts_app_server_resume_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread(
        "thread-1",
        [
            _FakeAppTurnStream(
                [
                    _item_completed_notification("Resumed", thread_id="thread-1"),
                    _turn_completed_notification(thread_id="thread-1"),
                ]
            )
        ],
    )
    fake_client = _FakeAppServerClient(start_thread=fake_thread, resume_thread=fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    resume_options = AppServerThreadResumeOptions(cwd="/tmp/project")
    thread = client.resume_thread("thread-1", resume_options)

    assert thread.id == "thread-1"
    assert thread.run_text("continue") == "Resumed"
    assert fake_client.resume_calls[0] == ("thread-1", resume_options)


def test_run_can_parse_final_json_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = '{"answer":"structured summary"}'
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_item_completed_notification(payload), _turn_completed_notification()]
            ),
            _FakeAppTurnStream(
                [_item_completed_notification(payload), _turn_completed_notification()]
            ),
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread = client.start_thread()

    assert thread.run_json("return JSON") == {"answer": "structured summary"}
    assert thread.run_model("return JSON", SummaryModel) == SummaryModel(
        answer="structured summary"
    )
    _, model_options = fake_thread.run_calls[1]
    assert isinstance(model_options, AppServerTurnOptions)
    assert model_options.output_schema is SummaryModel


def test_run_model_accepts_app_server_turn_options(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = '{"answer":"structured summary"}'
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_item_completed_notification(payload), _turn_completed_notification()]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    thread = Codex().start_thread()
    options = AppServerTurnOptions(model="gpt-5")

    assert thread.run_model("return JSON", SummaryModel, options) == SummaryModel(
        answer="structured summary"
    )

    _, model_options = fake_thread.run_calls[0]
    assert isinstance(model_options, AppServerTurnOptions)
    assert model_options.model == "gpt-5"
    assert model_options.output_schema is SummaryModel


def test_run_requires_final_assistant_message_for_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread("thr-1", [_FakeAppTurnStream([_turn_completed_notification()])])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    stream = Codex().start_thread().run("return JSON")
    stream.wait()

    with pytest.raises(ValueError, match="No final message is available yet"):
        stream.final_json()

    with pytest.raises(ValueError, match="No final message is available yet"):
        stream.final_model(SummaryModel)


def test_run_model_rejects_conflicting_output_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread("thr-1", [])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    thread = Codex().start_thread()

    with pytest.raises(ValueError, match="Thread.run_model\\(\\) received both model_type"):
        thread.run_model(
            "return JSON",
            SummaryModel,
            TurnOptions(output_schema={"type": "object"}),
        )


def test_run_passes_process_thread_and_turn_options_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [_FakeAppTurnStream([_item_completed_notification("ok"), _turn_completed_notification()])],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    capture: dict[str, object] = {}
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture=capture)

    client = Codex(
        CodexOptions(
            codex_path_override="/tmp/codex",
            base_url="http://example.test",
            api_key="key",
            config={"profile": "dev"},
            env={"CUSTOM_ENV": "1"},
        )
    )
    requested_start_options = ThreadStartOptions(
        model="gpt-test-1",
        cwd="/tmp/project",
        approval_policy=protocol.AskForApproval("on-request"),
        sandbox=protocol.SandboxMode("workspace-write"),
        config={
            "skip_git_repo_check": True,
            "web_search": "cached",
        },
    )
    turn_options = TurnOptions(
        model="gpt-test-1",
        cwd="/tmp/project",
        approval_policy=protocol.AskForApproval("on-request"),
        effort=protocol.ReasoningEffort("none"),
        output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        sandbox_policy=protocol.SandboxPolicy.model_validate(
            {
                "type": "workspaceWrite",
                "writableRoots": ["/tmp/project", "/tmp/backend", "/tmp/shared"],
                "networkAccess": True,
            }
        ),
    )
    thread = client.start_thread(requested_start_options)

    assert thread.run_text("hello", turn_options) == "ok"

    process_options = capture["process_options"]
    assert process_options == AppServerProcessOptions(
        codex_path_override="/tmp/codex",
        base_url="http://example.test",
        api_key="key",
        config={"profile": "dev"},
        env={"CUSTOM_ENV": "1"},
    )
    assert fake_client.account.login_api_key_calls == ["key"]

    start_options, tools = fake_client.start_calls[0]
    assert isinstance(start_options, AppServerThreadStartOptions)
    assert start_options == requested_start_options.to_app_server_options()
    assert tools is None

    _, run_options = fake_thread.run_calls[0]
    assert isinstance(run_options, AppServerTurnOptions)
    assert run_options == turn_options.to_app_server_options()


def test_run_turn_signal_interrupts_in_flight_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_thread = _FakeAppThread("thr-1", [_InterruptibleFakeTurnStream()])
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread = client.start_thread()
    signal = threading.Event()
    stream = thread.run("hello", signal=signal)

    signal.set()

    with pytest.raises(ThreadRunError, match="Turn aborted: interrupted"):
        stream.wait()

    fake_stream = fake_thread.run_calls[0]
    _ = fake_stream


def test_run_raises_thread_run_error_for_failed_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_turn_completed_notification(status="failed", error_message="request failed")]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread = client.start_thread()

    with pytest.raises(ThreadRunError, match="request failed") as exc_info:
        thread.run_text("hello")

    assert exc_info.value.turn is not None
    assert exc_info.value.terminal_status == "failed"
    assert exc_info.value.turn.error is not None
    assert exc_info.value.turn.error.message == "request failed"


def test_codex_run_text_preserves_thread_run_error_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_turn_completed_notification(status="failed", error_message="request failed")]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()

    with pytest.raises(ThreadRunError, match="request failed") as exc_info:
        client.run_text("hello")

    assert exc_info.value.turn is not None
    assert exc_info.value.turn.id == "turn-1"
    assert exc_info.value.terminal_status == "failed"
    assert exc_info.value.turn.error is not None
    assert exc_info.value.turn.error.message == "request failed"


def test_codex_run_json_preserves_thread_run_error_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_turn_completed_notification(status="failed", error_message="request failed")]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()

    with pytest.raises(ThreadRunError, match="request failed") as exc_info:
        client.run_json("hello")

    assert exc_info.value.turn is not None
    assert exc_info.value.turn.id == "turn-1"
    assert exc_info.value.terminal_status == "failed"
    assert exc_info.value.turn.error is not None
    assert exc_info.value.turn.error.message == "request failed"


def test_codex_run_model_preserves_thread_run_error_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_turn_completed_notification(status="failed", error_message="request failed")]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()

    with pytest.raises(ThreadRunError, match="request failed") as exc_info:
        client.run_model("hello", SummaryModel)

    assert exc_info.value.turn is not None
    assert exc_info.value.turn.id == "turn-1"
    assert exc_info.value.terminal_status == "failed"
    assert exc_info.value.turn.error is not None
    assert exc_info.value.turn.error.message == "request failed"


def test_run_normalizes_structured_input_for_app_server(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_thread = _FakeAppThread(
        "thr-1",
        [
            _FakeAppTurnStream(
                [_item_completed_notification("done"), _turn_completed_notification()]
            )
        ],
    )
    fake_client = _FakeAppServerClient(fake_thread)
    _patch_connect_stdio(monkeypatch, fake_client=fake_client, capture={})

    client = Codex()
    thread = client.start_thread()

    thread.run_text(
        [
            {"type": "text", "text": "Describe file changes"},
            {"type": "text", "text": "Focus on impacted tests"},
            {"type": "localImage", "path": "/tmp/first.png"},
            {"type": "localImage", "path": "/tmp/second.jpg"},
        ]
    )

    run_input, _ = fake_thread.run_calls[0]
    assert run_input == [
        {"type": "text", "text": "Describe file changes"},
        {"type": "text", "text": "Focus on impacted tests"},
        {"type": "localImage", "path": "/tmp/first.png"},
        {"type": "localImage", "path": "/tmp/second.jpg"},
    ]
