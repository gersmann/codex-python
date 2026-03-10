from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from queue import Queue
from typing import Any

import pytest
from pydantic import BaseModel

from codex.app_server import (
    AppServerClient,
    AppServerClientInfo,
    AppServerInitializeOptions,
    AppServerRpcError,
    AsyncAppServerClient,
)
from codex.app_server.client import _LoopThread
from codex.protocol import types as protocol

JsonObject = dict[str, Any]


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


class SummaryModel(BaseModel):
    answer: str


class ScriptedTransport:
    def __init__(self) -> None:
        self.sent: list[JsonObject] = []
        self.responses: dict[str, JsonObject | Callable[[JsonObject], JsonObject]] = {}
        self.started = False
        self.closed = False
        self._incoming: Queue[JsonObject | None] = Queue()

    async def start(self) -> None:
        self.started = True

    async def send(self, message: JsonObject) -> None:
        self.sent.append(message)
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


def _wait_until(predicate: Callable[[], bool], timeout: float = 1.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


def _turn_start_count(transport: ScriptedTransport) -> int:
    return sum(1 for message in transport.sent if message.get("method") == "turn/start")


def test_async_client_start_thread_returns_thread_object() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        client = AsyncAppServerClient(
            transport,
            AppServerInitializeOptions(
                client_info=AppServerClientInfo(
                    name="pytest-client",
                    title="Pytest Client",
                    version="1.2.3",
                ),
                experimental_api=True,
                opt_out_notification_methods=("item/agentMessage/delta",),
            ),
        )

        await client.start()
        thread = await client.start_thread()

        assert transport.started is True
        assert transport.sent[0]["method"] == "initialize"
        assert transport.sent[0]["params"]["clientInfo"] == {
            "name": "pytest-client",
            "title": "Pytest Client",
            "version": "1.2.3",
        }
        assert transport.sent[0]["params"]["capabilities"] == {
            "experimentalApi": True,
            "optOutNotificationMethods": ["item/agentMessage/delta"],
        }
        assert transport.sent[1] == {"method": "initialized", "params": {}}
        assert transport.sent[2] == {"id": 1, "method": "thread/start", "params": {}}
        assert thread.id == "thr-1"
        assert isinstance(thread.snapshot, protocol.Thread)
        assert thread.snapshot.cwd == "/repo"

        await client.close()

    asyncio.run(scenario())


def test_async_turn_stream_yields_typed_events_and_aggregates_final_text() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_turn(message: JsonObject) -> JsonObject:
            assert message["params"]["threadId"] == "thr-1"
            assert message["params"]["input"] == [{"type": "text", "text": "Summarize this repo."}]
            return {"id": message["id"], "result": {"turn": _turn_payload()}}

        transport.responses["turn/start"] = start_turn
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()
        stream = await thread.run("Summarize this repo.")

        transport.push(
            {
                "method": "turn/started",
                "params": {"threadId": "thr-1", "turn": _turn_payload()},
            }
        )
        transport.push(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "itemId": "item-1",
                    "delta": "Repository summary",
                },
            }
        )
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("Repository summary"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(status="completed"),
                },
            }
        )

        events = [event async for event in stream]

        assert [type(event) for event in events] == [
            protocol.TurnStartedNotificationModel,
            protocol.ItemAgentMessageDeltaNotification,
            protocol.ItemCompletedNotificationModel,
            protocol.TurnCompletedNotificationModel,
        ]
        assert events[1].params.delta == "Repository summary"
        assert isinstance(events[2].params.item.root, protocol.AgentMessageThreadItem)
        assert stream.final_text == "Repository summary"
        assert stream.final_message is not None
        assert stream.final_message.text == "Repository summary"
        assert stream.final_message.phase is not None
        assert stream.final_message.phase.root == "final_answer"
        assert stream.final_turn is not None
        assert stream.final_turn.status.root == "completed"
        assert isinstance(stream.items[0].root, protocol.AgentMessageThreadItem)

        await client.close()

    asyncio.run(scenario())


def test_async_thread_run_text_json_and_model_helpers() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        transport.responses["turn/start"] = {"turn": _turn_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()

        async def push_turn_result(text: str) -> None:
            await asyncio.sleep(0)
            transport.push(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turnId": "turn-1",
                        "item": _agent_message_item(text),
                    },
                }
            )
            transport.push(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turn": _turn_payload(status="completed"),
                    },
                }
            )

        text_task = asyncio.create_task(thread.run_text("Summarize this repo."))
        await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 1)
        await push_turn_result("Async summary")
        assert await text_task == "Async summary"

        json_task = asyncio.create_task(thread.run_json("Return JSON"))
        await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 2)
        await push_turn_result('{"answer":"async structured summary"}')
        assert await json_task == {"answer": "async structured summary"}

        model_task = asyncio.create_task(thread.run_model("Return JSON", SummaryModel))
        await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 3)
        await push_turn_result('{"answer":"async model summary"}')
        assert await model_task == SummaryModel(answer="async model summary")

        await client.close()

    asyncio.run(scenario())


def test_async_client_parses_typed_server_requests() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        client = AsyncAppServerClient(transport)
        await client.start()

        seen: list[protocol.ItemToolCallRequest] = []

        def handle_tool_call(request: protocol.ItemToolCallRequest) -> JsonObject:
            seen.append(request)
            assert request.params.tool == "lookup_ticket"
            assert request.params.arguments == {"id": "123"}
            return {"echo": request.params.tool}

        client.on_request(
            "item/tool/call",
            handle_tool_call,
            request_model=protocol.ItemToolCallRequest,
        )

        transport.push(
            {
                "id": "req-1",
                "method": "item/tool/call",
                "params": {
                    "callId": "call-1",
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "tool": "lookup_ticket",
                    "arguments": {"id": "123"},
                },
            }
        )

        await asyncio.to_thread(
            _wait_until,
            lambda: any(message.get("id") == "req-1" for message in transport.sent),
        )

        assert len(seen) == 1
        assert transport.sent[-1] == {"id": "req-1", "result": {"echo": "lookup_ticket"}}

        await client.close()

    asyncio.run(scenario())


def test_async_client_raises_rpc_error() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()

        def failing_response(message: JsonObject) -> JsonObject:
            return {
                "id": message["id"],
                "error": {"code": 123, "message": "boom", "data": {"detail": "bad"}},
            }

        transport.responses["thread/start"] = failing_response
        client = AsyncAppServerClient(transport)
        await client.start()

        with pytest.raises(AppServerRpcError, match="boom") as exc_info:
            await client.start_thread()

        assert exc_info.value.code == 123
        assert exc_info.value.data == {"detail": "bad"}

        await client.close()

    asyncio.run(scenario())


def test_sync_client_exposes_oo_thread_and_stream_api() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    transport.responses["turn/start"] = {"turn": _turn_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()
        stream = thread.run("Summarize this repo.")
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item("Synchronous summary"),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(status="completed"),
                },
            }
        )
        stream.wait()

        assert thread.id == "thr-1"
        assert stream.final_text == "Synchronous summary"
        assert stream.final_message is not None
        assert stream.final_message.text == "Synchronous summary"
        assert stream.final_turn is not None
        assert stream.final_turn.status.root == "completed"
    finally:
        client.close()


def test_turn_stream_can_parse_final_json_and_model() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    transport.responses["turn/start"] = {"turn": _turn_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()
        stream = thread.run("Return JSON")
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": _agent_message_item('{"answer":"structured summary"}'),
                },
            }
        )
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(status="completed"),
                },
            }
        )

        stream.wait()

        assert stream.final_json() == {"answer": "structured summary"}
        assert stream.final_model(SummaryModel) == SummaryModel(answer="structured summary")
    finally:
        client.close()


def test_sync_thread_run_text_json_and_model_helpers() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    transport.responses["turn/start"] = {"turn": _turn_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()

        def push_turn_result(text: str) -> None:
            transport.push(
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turnId": "turn-1",
                        "item": _agent_message_item(text),
                    },
                }
            )
            transport.push(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turn": _turn_payload(status="completed"),
                    },
                }
            )

        async def run_in_threadpool() -> None:
            text_future = asyncio.create_task(
                asyncio.to_thread(thread.run_text, "Summarize this repo.")
            )
            await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 1)
            push_turn_result("Sync summary")
            assert await text_future == "Sync summary"

            json_future = asyncio.create_task(asyncio.to_thread(thread.run_json, "Return JSON"))
            await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 2)
            push_turn_result('{"answer":"sync structured summary"}')
            assert await json_future == {"answer": "sync structured summary"}

            model_future = asyncio.create_task(
                asyncio.to_thread(thread.run_model, "Return JSON", SummaryModel)
            )
            await asyncio.to_thread(_wait_until, lambda: _turn_start_count(transport) >= 3)
            push_turn_result('{"answer":"sync model summary"}')
            assert await model_future == SummaryModel(answer="sync model summary")

        asyncio.run(run_in_threadpool())
    finally:
        client.close()
