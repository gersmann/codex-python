from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import BaseModel

from codex.errors import CodexParseError, ThreadRunError
from codex.exec import CodexExecArgs
from codex.options import CodexOptions, ThreadOptions, TurnOptions
from codex.protocol import types as protocol
from codex.thread import Thread


class SummaryModel(BaseModel):
    answer: str


class FakeExec:
    def __init__(self, batches: list[list[BaseModel]]) -> None:
        self._batches = [
            [event.model_dump_json(by_alias=True) for event in batch] for batch in batches
        ]
        self.calls: list[CodexExecArgs] = []

    def run(self, args: CodexExecArgs) -> Iterator[str]:
        self.calls.append(args)
        call_index = len(self.calls) - 1
        if call_index >= len(self._batches):
            raise AssertionError("Unexpected extra exec call")
        yield from self._batches[call_index]


def _session_configured(thread_id: str) -> protocol.SessionConfiguredEventMsg:
    return protocol.SessionConfiguredEventMsg(
        type="session_configured",
        approval_policy="never",
        cwd="/repo",
        history_entry_count=0,
        history_log_id=1,
        model="gpt-test-1",
        model_provider_id="openai",
        sandbox_policy={"type": "dangerFullAccess"},
        session_id=thread_id,
    )


def _task_started(turn_id: str = "turn-1") -> protocol.TaskStartedEventMsg:
    return protocol.TaskStartedEventMsg(type="task_started", turn_id=turn_id)


def _agent_message_item(text: str, item_id: str = "item-1") -> protocol.TurnItem:
    return protocol.TurnItem.model_validate(
        {
            "id": item_id,
            "type": "AgentMessage",
            "content": [{"type": "Text", "text": text}],
        }
    )


def _token_count(
    *,
    input_tokens: int = 42,
    cached_input_tokens: int = 12,
    output_tokens: int = 5,
) -> protocol.TokenCountEventMsg:
    total_tokens = input_tokens + cached_input_tokens + output_tokens
    return protocol.TokenCountEventMsg(
        type="token_count",
        info={
            "last_token_usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": 0,
                "total_tokens": total_tokens,
            },
            "total_token_usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": 0,
                "total_tokens": total_tokens,
            },
        },
    )


def _success_events(thread_id: str, text: str) -> list[BaseModel]:
    return [
        _session_configured(thread_id),
        _task_started(),
        protocol.AgentMessageDeltaEventMsg(type="agent_message_delta", delta=text),
        protocol.ItemCompletedEventMsg(
            type="item_completed",
            thread_id=thread_id,
            turn_id="turn-1",
            item=_agent_message_item(text),
        ),
        _token_count(),
        protocol.TaskCompleteEventMsg(
            type="task_complete",
            turn_id="turn-1",
            last_agent_message=text,
        ),
    ]


def test_run_returns_typed_stream_and_aggregates_state() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    stream = thread.run("hello")
    events = list(stream)

    assert [type(event) for event in events] == [
        protocol.SessionConfiguredEventMsg,
        protocol.TaskStartedEventMsg,
        protocol.AgentMessageDeltaEventMsg,
        protocol.ItemCompletedEventMsg,
        protocol.TokenCountEventMsg,
        protocol.TaskCompleteEventMsg,
    ]
    assert thread.id == "thread-1"
    assert stream.turn_id == "turn-1"
    assert stream.final_text == "Hi!"
    assert stream.usage == protocol.TokenUsage(
        input_tokens=42,
        cached_input_tokens=12,
        output_tokens=5,
        reasoning_output_tokens=0,
        total_tokens=59,
    )
    assert len(stream.items) == 1
    assert fake_exec.calls[0].input == "hello"
    assert fake_exec.calls[0].thread_id is None


def test_run_text_twice_reuses_thread_id() -> None:
    fake_exec = FakeExec(
        [_success_events("thread-1", "First"), _success_events("thread-1", "Second")]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    first = thread.run_text("first input")
    second = thread.run_text("second input")

    assert first == "First"
    assert second == "Second"
    assert fake_exec.calls[1].thread_id == "thread-1"
    assert fake_exec.calls[1].input == "second input"


def test_resume_thread_uses_given_id() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Resumed")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions(), thread_id="thread-1")

    result = thread.run_text("continue")

    assert result == "Resumed"
    assert fake_exec.calls[0].thread_id == "thread-1"


def test_run_can_parse_final_json_and_model() -> None:
    fake_exec = FakeExec(
        [
            _success_events("thread-1", '{"answer":"structured summary"}'),
            _success_events("thread-1", '{"answer":"structured summary"}'),
        ]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    assert thread.run_json("return JSON") == {"answer": "structured summary"}
    assert thread.run_model("return JSON", SummaryModel) == SummaryModel(
        answer="structured summary"
    )


def test_run_forwards_thread_options() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    options = ThreadOptions(
        model="gpt-test-1",
        sandbox_mode="workspace-write",
        working_directory="/tmp/project",
        skip_git_repo_check=True,
        model_reasoning_effort="high",
        network_access_enabled=True,
        web_search_mode="cached",
        web_search_enabled=False,
        approval_policy="on-request",
        additional_directories=["../backend", "/tmp/shared"],
    )
    thread = Thread(fake_exec, CodexOptions(base_url="http://example.test", api_key="key"), options)

    thread.run_text("hello")

    call = fake_exec.calls[0]
    assert call.model == "gpt-test-1"
    assert call.sandbox_mode == "workspace-write"
    assert call.working_directory == "/tmp/project"
    assert call.skip_git_repo_check is True
    assert call.base_url == "http://example.test"
    assert call.api_key == "key"
    assert call.model_reasoning_effort == "high"
    assert call.network_access_enabled is True
    assert call.web_search_mode == "cached"
    assert call.web_search_enabled is False
    assert call.approval_policy == "on-request"
    assert call.additional_directories == ["../backend", "/tmp/shared"]


def test_run_forwards_turn_signal() -> None:
    class AbortFlag:
        def __init__(self) -> None:
            self.aborted = False

    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())
    signal = AbortFlag()

    thread.run_text("hello", TurnOptions(signal=signal))

    assert fake_exec.calls[0].signal is signal


def test_run_writes_and_cleans_output_schema_file() -> None:
    schema_paths: list[Path] = []

    class SchemaExec:
        calls: list[CodexExecArgs]

        def __init__(self) -> None:
            self.calls = []

        def run(self, args: CodexExecArgs) -> Iterator[str]:
            self.calls.append(args)
            if args.output_schema_file is None:
                raise AssertionError("expected output_schema_file to be set")
            schema_path = Path(args.output_schema_file)
            assert schema_path.exists()
            schema_paths.append(schema_path)
            yield from (
                event.model_dump_json(by_alias=True) for event in _success_events("thread-1", "ok")
            )

    fake_exec = SchemaExec()
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())
    schema: dict[str, object] = {"type": "object", "properties": {"answer": {"type": "string"}}}
    assert thread.run_text("hello", TurnOptions(output_schema=schema)) == "ok"

    assert len(schema_paths) == 1
    assert not schema_paths[0].exists()


def test_run_normalizes_structured_input_and_forwards_images() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "done")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    thread.run_text(
        [
            {"type": "text", "text": "Describe file changes"},
            {"type": "text", "text": "Focus on impacted tests"},
            {"type": "local_image", "path": "/tmp/first.png"},
            {"type": "local_image", "path": "/tmp/second.jpg"},
        ]
    )

    call = fake_exec.calls[0]
    assert call.input == "Describe file changes\n\nFocus on impacted tests"
    assert call.images == ["/tmp/first.png", "/tmp/second.jpg"]


def test_run_text_raises_thread_run_error_on_error_event() -> None:
    fake_exec = FakeExec(
        [
            [
                _session_configured("thread-1"),
                _task_started(),
                protocol.ErrorEventMsg(type="error", message="rate limit exceeded"),
            ]
        ]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    with pytest.raises(ThreadRunError, match="rate limit exceeded"):
        thread.run_text("hello")


def test_run_returns_partial_text_when_stream_disconnects_before_completion() -> None:
    fake_exec = FakeExec(
        [
            [
                _session_configured("thread-1"),
                _task_started(),
                protocol.AgentMessageEventMsg(type="agent_message", message="partial"),
            ]
        ]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    stream = thread.run("hello")
    stream.wait()

    assert stream.final_text == "partial"
    assert stream.usage is None


def test_run_raises_parse_error_for_invalid_json_event() -> None:
    class InvalidExec:
        def run(self, args: CodexExecArgs) -> Iterator[str]:
            _ = args
            yield "not-json"

    thread = Thread(InvalidExec(), CodexOptions(), ThreadOptions())
    with pytest.raises(CodexParseError):
        thread.run_text("hello")
