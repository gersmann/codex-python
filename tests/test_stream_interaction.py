from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from queue import Queue
from typing import Any

import pytest

from codex.app_server import AppServerClient, AsyncAppServerClient
from codex.app_server._sync_client import _LoopThread
from codex.protocol import types as protocol

JsonObject = dict[str, Any]


# Keep payload helpers aligned with tests/test_app_server_client.py.
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


# Inlined from tests/test_app_server_client.py pattern.
class ScriptedTransport:
    def __init__(self) -> None:
        self.sent: list[JsonObject] = []
        self.responses: dict[str, JsonObject | Callable[[JsonObject], JsonObject]] = {}
        self.started = False
        self.closed = False
        self._sent_condition = threading.Condition()
        self._incoming: Queue[JsonObject | None] = Queue()

    async def start(self) -> None:
        self.started = True

    async def send(self, message: JsonObject) -> None:
        with self._sent_condition:
            self.sent.append(message)
            self._sent_condition.notify_all()
        if "id" in message and message.get("method") == "initialize":
            self.push({"id": message["id"], "result": {"userAgent": "test-client"}})
            return
        method = message.get("method")
        if "id" in message and isinstance(method, str) and method in self.responses:
            response = self.responses[method]
            if callable(response):
                self.push(response(message))
            else:
                self.push({"id": message["id"], "result": response})

    async def receive(self) -> JsonObject | None:
        return await asyncio.to_thread(self._incoming.get)

    async def close(self) -> None:
        self.closed = True
        self.push(None)

    def push(self, message: JsonObject | None) -> None:
        self._incoming.put(message)

    def wait_for_method(
        self,
        method: str,
        *,
        count: int = 1,
        timeout: float = 1.0,
    ) -> JsonObject:
        deadline = time.monotonic() + timeout
        with self._sent_condition:
            while True:
                matching = [message for message in self.sent if message.get("method") == method]
                if len(matching) >= count:
                    return matching[count - 1]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError(f"expected {count} '{method}' message(s) within timeout")
                self._sent_condition.wait(remaining)


def _make_sync_client() -> tuple[AppServerClient, ScriptedTransport]:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}

    turn_count = {"value": 0}

    def start_turn(message: JsonObject) -> JsonObject:
        _ = message
        turn_count["value"] += 1
        return {
            "id": message["id"],
            "result": {"turn": _turn_payload(turn_id=f"turn-{turn_count['value']}")},
        }

    transport.responses["turn/start"] = start_turn

    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    return AppServerClient(async_client, loop), transport


def _wait_with_timeout(stream: object, timeout_seconds: float = 2.0) -> None:
    done = threading.Event()
    error: list[BaseException] = []

    def _target() -> None:
        try:
            stream.wait()
        except BaseException as exc:  # surfaced back to test thread
            error.append(exc)
        finally:
            done.set()

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    if not done.wait(timeout_seconds):
        pytest.fail(f"stream.wait() did not return within {timeout_seconds:.1f}s")
    worker.join(timeout=0.1)
    if error:
        raise error[0]


def _consume_like_review_action(stream: object) -> tuple[bool, list[protocol.Notification]]:
    """Reproduce codex-review-action's _consume_turn behavior.

    Pattern reproduced:
      for event in stream:
          if isinstance(event, TurnCompletedNotificationModel):
              task_complete = True
              break
      stream.wait()
    """

    task_complete = False
    events: list[protocol.Notification] = []
    for event in stream:
        events.append(event)
        if isinstance(event, protocol.TurnCompletedNotificationModel):
            task_complete = True
            break

    _wait_with_timeout(stream, timeout_seconds=2.0)
    return task_complete, events


def test_consume_natural_completion() -> None:
    """Review-action compatibility: consume entire stream naturally, then wait()."""

    client, transport = _make_sync_client()
    try:
        thread = client.start_thread()
        stream = thread.run("Natural completion")

        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("Natural completion text"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(turn_id="turn-1", status="completed"),
                },
            }
        )

        events = [event for event in stream]
        _wait_with_timeout(stream, timeout_seconds=2.0)

        assert [type(event) for event in events] == [
            protocol.ItemCompletedNotificationModel,
            protocol.TurnCompletedNotificationModel,
        ]
        assert stream.final_text == "Natural completion text"
        assert stream.final_turn is not None
        assert stream.final_turn.status.root == "completed"
    finally:
        client.close()


def test_consume_break_on_turn_completed() -> None:
    """Review-action compatibility: break on TurnCompleted, then call wait()."""

    client, transport = _make_sync_client()
    try:
        thread = client.start_thread()
        stream = thread.run("Break on terminal")

        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("Break-on-complete text"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(turn_id="turn-1", status="completed"),
                },
            }
        )

        task_complete, events = _consume_like_review_action(stream)

        assert task_complete is True
        assert isinstance(events[-1], protocol.TurnCompletedNotificationModel)
        assert stream.final_text == "Break-on-complete text"
    finally:
        client.close()


def test_consume_two_turns_same_thread() -> None:
    """Review-action execute_structured pattern: two consecutive thread.run() calls."""

    client, transport = _make_sync_client()
    try:
        thread = client.start_thread()

        stream1 = thread.run("First pass")
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("First pass text"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(turn_id="turn-1", status="completed"),
                },
            }
        )
        task_complete_1, _ = _consume_like_review_action(stream1)

        stream2 = thread.run("Schema pass")
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-2",
                    "item": _agent_message_item("Second pass text"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(turn_id="turn-2", status="completed"),
                },
            }
        )
        task_complete_2, _ = _consume_like_review_action(stream2)

        assert task_complete_1 is True
        assert task_complete_2 is True
        assert stream1.final_text == "First pass text"
        assert stream2.final_text == "Second pass text"

        # Ensure two turn/start calls were made for the same thread object.
        first = transport.wait_for_method("turn/start", count=1)
        second = transport.wait_for_method("turn/start", count=2)
        assert first["params"]["threadId"] == "thr-1"
        assert second["params"]["threadId"] == "thr-1"
    finally:
        client.close()


def test_turn_completed_not_in_notification_methods_does_not_hang() -> None:
    """Reproduce review-action handling when terminalInteraction is emitted.

    codex-review-action handles `item/commandExecution/terminalInteraction`, but
    `_TURN_STREAM_NOTIFICATION_METHODS` does not subscribe to that method.
    This test verifies such events are effectively dropped for the turn stream and
    do not cause `wait()` to hang.
    """

    client, transport = _make_sync_client()
    try:
        thread = client.start_thread()
        stream = thread.run("Terminal interaction compatibility")

        # This method is intentionally *not* part of turn stream subscribed methods.
        transport.push(
            {
                "method": "item/commandExecution/terminalInteraction",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "itemId": "cmd-1",
                    "processId": "proc-1",
                    "stdin": "y",
                },
            }
        )
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("Post interaction text"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(turn_id="turn-1", status="completed"),
                },
            }
        )

        task_complete, events = _consume_like_review_action(stream)

        assert task_complete is True
        # If terminalInteraction had been routed to stream, we'd see an extra event.
        assert [type(event) for event in events] == [
            protocol.ItemCompletedNotificationModel,
            protocol.TurnCompletedNotificationModel,
        ]
        assert stream.final_text == "Post interaction text"
    finally:
        client.close()
