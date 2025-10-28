from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from codex.errors import CodexParseError, ThreadRunError
from codex.exec import CodexExecArgs
from codex.options import CodexOptions, ThreadOptions, TurnOptions
from codex.thread import Thread


class FakeExec:
    def __init__(self, batches: list[list[dict[str, object]]]) -> None:
        self._batches = [[json.dumps(event) for event in batch] for batch in batches]
        self.calls: list[CodexExecArgs] = []

    def run(self, args: CodexExecArgs) -> Iterator[str]:
        self.calls.append(args)
        call_index = len(self.calls) - 1
        if call_index >= len(self._batches):
            raise AssertionError("Unexpected extra exec call")
        yield from self._batches[call_index]


def _success_events(thread_id: str, text: str) -> list[dict[str, object]]:
    return [
        {"type": "thread.started", "thread_id": thread_id},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item-1", "type": "agent_message", "text": text}},
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 42, "cached_input_tokens": 12, "output_tokens": 5},
        },
    ]


def test_run_returns_items_usage_and_thread_id() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    result = thread.run("hello")

    assert thread.id == "thread-1"
    assert result.final_response == "Hi!"
    assert result.usage == {"input_tokens": 42, "cached_input_tokens": 12, "output_tokens": 5}
    assert len(result.items) == 1
    assert fake_exec.calls[0].input == "hello"
    assert fake_exec.calls[0].thread_id is None


def test_run_twice_reuses_thread_id() -> None:
    fake_exec = FakeExec(
        [_success_events("thread-1", "First"), _success_events("thread-1", "Second")]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    first = thread.run("first input")
    second = thread.run("second input")

    assert first.final_response == "First"
    assert second.final_response == "Second"
    assert fake_exec.calls[1].thread_id == "thread-1"
    assert fake_exec.calls[1].input == "second input"


def test_resume_thread_uses_given_id() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Resumed")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions(), thread_id="thread-1")

    result = thread.run("continue")

    assert result.final_response == "Resumed"
    assert fake_exec.calls[0].thread_id == "thread-1"


def test_run_streamed_yields_events() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    streamed = thread.run_streamed("hello")
    events = list(streamed.events)

    assert [event["type"] for event in events] == [
        "thread.started",
        "turn.started",
        "item.completed",
        "turn.completed",
    ]
    assert thread.id == "thread-1"


def test_run_forwards_thread_options() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "Hi!")])
    options = ThreadOptions(
        model="gpt-test-1",
        sandbox_mode="workspace-write",
        working_directory="/tmp/project",
        skip_git_repo_check=True,
    )
    thread = Thread(fake_exec, CodexOptions(base_url="http://example.test", api_key="key"), options)

    thread.run("hello")

    call = fake_exec.calls[0]
    assert call.model == "gpt-test-1"
    assert call.sandbox_mode == "workspace-write"
    assert call.working_directory == "/tmp/project"
    assert call.skip_git_repo_check is True
    assert call.base_url == "http://example.test"
    assert call.api_key == "key"


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
            yield json.dumps({"type": "thread.started", "thread_id": "thread-1"})
            yield json.dumps({"type": "turn.started"})
            yield json.dumps(
                {
                    "type": "item.completed",
                    "item": {"id": "1", "type": "agent_message", "text": "ok"},
                }
            )
            yield json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1},
                }
            )

    fake_exec = SchemaExec()
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    thread.run("hello", TurnOptions(output_schema=schema))

    assert len(schema_paths) == 1
    assert not schema_paths[0].exists()


def test_run_normalizes_structured_input_and_forwards_images() -> None:
    fake_exec = FakeExec([_success_events("thread-1", "done")])
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    thread.run(
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


def test_run_raises_thread_run_error_on_turn_failure() -> None:
    fake_exec = FakeExec(
        [
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.started"},
                {"type": "turn.failed", "error": {"message": "rate limit exceeded"}},
            ]
        ]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    with pytest.raises(ThreadRunError, match="rate limit exceeded"):
        thread.run("hello")


def test_run_raises_when_stream_disconnects_before_completion() -> None:
    fake_exec = FakeExec(
        [
            [
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {"id": "1", "type": "agent_message", "text": "partial"},
                },
            ]
        ]
    )
    thread = Thread(fake_exec, CodexOptions(), ThreadOptions())

    with pytest.raises(ThreadRunError, match="stream disconnected before completion"):
        thread.run("hello")


def test_run_raises_parse_error_for_invalid_json_event() -> None:
    class InvalidExec:
        def run(self, args: CodexExecArgs) -> Iterator[str]:
            _ = args
            yield "not-json"

    thread = Thread(InvalidExec(), CodexOptions(), ThreadOptions())
    with pytest.raises(CodexParseError):
        thread.run("hello")
