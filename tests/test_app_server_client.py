from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from queue import Queue
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

import codex
import codex.app_server as app_server_pkg
from codex.app_server import (
    AppServerClient,
    AppServerClientInfo,
    AppServerInitializeOptions,
    AppServerProtocolError,
    AppServerRpcError,
    AppServerThreadForkOptions,
    AppServerThreadListOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnError,
    AppServerTurnOptions,
    AppServerWebSocketOptions,
    AsyncAppServerClient,
    dynamic_tool,
)
from codex.app_server._sync_client import _LoopThread
from codex.app_server.models import EmptyResult, GenericNotification, GenericServerRequest
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


def _hook_run_payload(*, status: str = "running") -> JsonObject:
    payload: JsonObject = {
        "id": "hook-1",
        "displayOrder": 0,
        "entries": [],
        "eventName": "preToolUse",
        "executionMode": "sync",
        "handlerType": "command",
        "scope": "turn",
        "sourcePath": "/repo/.codex/hooks/pre_tool.py",
        "startedAt": 1730910000,
        "status": status,
    }
    if status != "running":
        payload["completedAt"] = 1730910001
        payload["durationMs"] = 1000
    return payload


class SummaryModel(BaseModel):
    answer: str


class ExperimentalFeatureListResponse(BaseModel):
    data: list[dict[str, object]]
    nextCursor: str | None = None


def _model_list_payload() -> JsonObject:
    return {
        "data": [
            {
                "id": "gpt-5.4",
                "model": "gpt-5.4",
                "displayName": "GPT-5.4",
                "description": "Primary model",
                "hidden": False,
                "defaultReasoningEffort": "medium",
                "supportedReasoningEfforts": [
                    {"reasoningEffort": "low", "description": "Lower latency"},
                    {"reasoningEffort": "medium", "description": "Balanced"},
                ],
                "inputModalities": ["text", "image"],
                "supportsPersonality": True,
                "isDefault": True,
                "upgrade": None,
                "upgradeInfo": None,
                "availabilityNux": None,
            }
        ],
        "nextCursor": None,
    }


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

    def wait_for_message(
        self,
        predicate: Callable[[JsonObject], bool],
        *,
        timeout: float = 1.0,
    ) -> JsonObject:
        deadline = time.monotonic() + timeout
        with self._sent_condition:
            while True:
                for message in self.sent:
                    if predicate(message):
                        return message
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError("expected transport message was not sent in time")
                self._sent_condition.wait(remaining)

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


def test_public_app_server_import_surface_exposes_only_intentional_sync_types() -> None:
    assert "RpcClient" in app_server_pkg.__all__
    assert "TurnStream" in app_server_pkg.__all__
    assert "AppServerClient" in app_server_pkg.__all__
    assert "AsyncAppServerClient" in app_server_pkg.__all__
    assert "AppServerWebSocketOptions" in app_server_pkg.__all__
    assert "GenericNotification" not in app_server_pkg.__all__
    assert "GenericServerRequest" not in app_server_pkg.__all__
    assert "AsyncStdioTransport" not in app_server_pkg.__all__
    assert "AsyncWebSocketTransport" not in app_server_pkg.__all__
    assert not hasattr(codex, "AppServerWebSocketOptions")

    assert "ModelsClient" not in app_server_pkg.__all__
    assert "AppsClient" not in app_server_pkg.__all__
    assert "SkillsClient" not in app_server_pkg.__all__
    assert "_LoopThread" not in app_server_pkg.__all__

    assert not hasattr(app_server_pkg, "ModelsClient")
    assert not hasattr(app_server_pkg, "_LoopThread")
    assert not hasattr(codex, "ModelsClient")
    assert not hasattr(codex, "_LoopThread")


def test_async_connect_websocket_passes_explicit_options_to_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeWebSocketTransport(ScriptedTransport):
        def __init__(self, url: str, options: AppServerWebSocketOptions | None) -> None:
            super().__init__()
            captured["url"] = url
            captured["options"] = options

    monkeypatch.setattr(
        "codex.app_server._async_client.AsyncWebSocketTransport",
        FakeWebSocketTransport,
    )

    async def scenario() -> None:
        websocket_options = AppServerWebSocketOptions(
            bearer_token="secret-token",
            headers={"X-Client": "pytest"},
        )
        client = await AsyncAppServerClient.connect_websocket(
            "ws://127.0.0.1:4500",
            websocket_options=websocket_options,
        )

        assert captured["url"] == "ws://127.0.0.1:4500"
        assert captured["options"] is websocket_options
        await client.close()

    asyncio.run(scenario())


def test_sync_connect_websocket_passes_explicit_options_to_async_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeService:
        async def list(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def list_page(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def write_config(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def read(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def login_api_key(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def login_chatgpt(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def login_chatgpt_tokens(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def cancel_login(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def logout(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def read_rate_limits(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def reload_mcp_servers(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def write_value(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def batch_write(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def read_requirements(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def oauth_login(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def list_status(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def list_status_page(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def upload(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def execute(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        exec = execute

        async def detect(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def import_items(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

        async def setup_start(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("not used")

    class FakeAsyncClient:
        def __init__(self) -> None:
            fake_service = FakeService()
            self.rpc = object()
            self.events = object()
            self.models = fake_service
            self.apps = fake_service
            self.skills = fake_service
            self.account = fake_service
            self.config = fake_service
            self.mcp_servers = fake_service
            self.feedback = fake_service
            self.command = fake_service
            self.external_agent_config = fake_service
            self.windows_sandbox = fake_service

        async def close(self) -> None:
            return None

    async def fake_connect_websocket(
        url: str,
        websocket_options: AppServerWebSocketOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> FakeAsyncClient:
        captured["url"] = url
        captured["websocket_options"] = websocket_options
        captured["initialize_options"] = initialize_options
        return FakeAsyncClient()

    monkeypatch.setattr(
        "codex.app_server._sync_client.AsyncAppServerClient.connect_websocket",
        fake_connect_websocket,
    )

    websocket_options = AppServerWebSocketOptions(
        bearer_token="secret-token",
        headers={"X-Client": "pytest"},
    )
    initialize_options = AppServerInitializeOptions()
    client = AppServerClient.connect_websocket(
        "ws://127.0.0.1:4500",
        websocket_options=websocket_options,
        initialize_options=initialize_options,
    )

    assert captured == {
        "url": "ws://127.0.0.1:4500",
        "websocket_options": websocket_options,
        "initialize_options": initialize_options,
    }
    client.close()


def test_async_connect_websocket_closes_transport_when_initialize_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FailingWebSocketTransport:
        def __init__(self, url: str, options: AppServerWebSocketOptions | None) -> None:
            _ = options
            captured["url"] = url
            captured["transport"] = self
            self.closed = False
            self._incoming: Queue[JsonObject | None] = Queue()

        async def start(self) -> None:
            return None

        async def send(self, message: JsonObject) -> None:
            if message.get("method") == "initialize" and "id" in message:
                self._incoming.put({"id": message["id"], "result": {"wrong": True}})

        async def receive(self) -> JsonObject | None:
            return await asyncio.to_thread(self._incoming.get)

        async def close(self) -> None:
            self.closed = True
            self._incoming.put(None)

    monkeypatch.setattr(
        "codex.app_server._async_client.AsyncWebSocketTransport",
        FailingWebSocketTransport,
    )

    async def scenario() -> None:
        with pytest.raises(
            AppServerProtocolError,
            match="Failed to parse app-server result for app-server method 'initialize'",
        ):
            await AsyncAppServerClient.connect_websocket("ws://127.0.0.1:4500")

    asyncio.run(scenario())

    assert captured["url"] == "ws://127.0.0.1:4500"
    assert cast(Any, captured["transport"]).closed is True


def test_sync_connect_websocket_closes_transport_when_initialize_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FailingWebSocketTransport:
        def __init__(self, url: str, options: AppServerWebSocketOptions | None) -> None:
            _ = options
            captured["url"] = url
            captured["transport"] = self
            self.closed = False
            self._incoming: Queue[JsonObject | None] = Queue()

        async def start(self) -> None:
            return None

        async def send(self, message: JsonObject) -> None:
            if message.get("method") == "initialize" and "id" in message:
                self._incoming.put({"id": message["id"], "result": {"wrong": True}})

        async def receive(self) -> JsonObject | None:
            return await asyncio.to_thread(self._incoming.get)

        async def close(self) -> None:
            self.closed = True
            self._incoming.put(None)

    monkeypatch.setattr(
        "codex.app_server._async_client.AsyncWebSocketTransport",
        FailingWebSocketTransport,
    )

    with pytest.raises(
        AppServerProtocolError,
        match="Failed to parse app-server result for app-server method 'initialize'",
    ):
        AppServerClient.connect_websocket("ws://127.0.0.1:4500")

    assert captured["url"] == "ws://127.0.0.1:4500"
    assert cast(Any, captured["transport"]).closed is True


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
        initialize_request = transport.wait_for_method("initialize")
        assert initialize_request["params"]["clientInfo"] == {
            "name": "pytest-client",
            "title": "Pytest Client",
            "version": "1.2.3",
        }
        assert initialize_request["params"]["capabilities"] == {
            "experimentalApi": True,
            "optOutNotificationMethods": ["item/agentMessage/delta"],
        }
        assert transport.wait_for_method("initialized") == {"method": "initialized", "params": {}}
        assert transport.wait_for_method("thread/start") == {
            "id": 1,
            "method": "thread/start",
            "params": {},
        }
        assert thread.id == "thr-1"
        assert isinstance(thread.snapshot, protocol.Thread)
        assert thread.snapshot.cwd.root == "/repo"

        await client.close()

    asyncio.run(scenario())


def test_app_server_thread_start_options_serialize_with_camel_case_aliases() -> None:
    params = AppServerThreadStartOptions(
        approval_policy=protocol.AskForApproval("never"),
        approvals_reviewer=protocol.ApprovalsReviewer("guardian_subagent"),
        base_instructions="Follow repo policy",
        experimental_raw_events=True,
        sandbox=protocol.SandboxMode("workspace-write"),
        service_name="pytest-client",
        session_start_source=protocol.ThreadStartSource("startup"),
    ).to_params()

    assert params.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=True,
        exclude_defaults=True,
    ) == {
        "approvalPolicy": "never",
        "approvalsReviewer": "guardian_subagent",
        "baseInstructions": "Follow repo policy",
        "experimentalRawEvents": True,
        "sandbox": "workspace-write",
        "serviceName": "pytest-client",
        "sessionStartSource": "startup",
    }


def test_app_server_thread_resume_and_fork_options_include_0_122_fields() -> None:
    resume_params = AppServerThreadResumeOptions(
        approvals_reviewer=protocol.ApprovalsReviewer("guardian_subagent"),
    ).to_params(thread_id="thr-1")
    fork_params = AppServerThreadForkOptions(
        approvals_reviewer=protocol.ApprovalsReviewer("guardian_subagent"),
        ephemeral=True,
    ).to_params(thread_id="thr-1")

    assert resume_params.model_dump(mode="python", by_alias=True, exclude_none=True) == {
        "approvalsReviewer": "guardian_subagent",
        "persistExtendedHistory": False,
        "threadId": "thr-1",
    }
    assert fork_params.model_dump(mode="python", by_alias=True, exclude_none=True) == {
        "approvalsReviewer": "guardian_subagent",
        "ephemeral": True,
        "persistExtendedHistory": False,
        "threadId": "thr-1",
    }


def test_app_server_turn_and_list_options_use_protocol_owned_types() -> None:
    turn_params = AppServerTurnOptions(
        approval_policy=protocol.AskForApproval("on-request"),
        approvals_reviewer=protocol.ApprovalsReviewer("guardian_subagent"),
        effort=protocol.ReasoningEffort("none"),
        personality=protocol.Personality("friendly"),
        responsesapi_client_metadata={"trace_id": "trace-1"},
        service_tier=protocol.ServiceTier("fast"),
        summary=protocol.ReasoningSummary("concise"),
    ).to_params(
        thread_id="thr-1",
        input=[{"type": "text", "text": "Summarize this repo."}],
    )
    list_params = AppServerThreadListOptions(
        sort_key=protocol.ThreadSortKey("updated_at"),
        source_kinds=[protocol.ThreadSourceKind("appServer")],
    ).to_params()

    assert turn_params.model_dump(mode="python", by_alias=True, exclude_none=True) == {
        "approvalPolicy": "on-request",
        "approvalsReviewer": "guardian_subagent",
        "effort": "none",
        "input": [{"type": "text", "text": "Summarize this repo.", "text_elements": []}],
        "personality": "friendly",
        "responsesapiClientMetadata": {"trace_id": "trace-1"},
        "serviceTier": "fast",
        "summary": "concise",
        "threadId": "thr-1",
    }
    assert list_params.model_dump(mode="python", by_alias=True, exclude_none=True) == {
        "sortKey": "updated_at",
        "sourceKinds": ["appServer"],
    }


def test_async_turn_stream_yields_typed_events_and_aggregates_final_text() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_turn(message: JsonObject) -> JsonObject:
            assert message["params"]["threadId"] == "thr-1"
            assert message["params"]["input"] == [{"type": "text", "text": "Summarize this repo."}]
            return {"id": message["id"], "result": {"turn": _turn_payload()}}

        def steer_turn(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "threadId": "thr-1",
                "expectedTurnId": "turn-1",
                "input": [{"type": "text", "text": "Add detail."}],
                "responsesapiClientMetadata": {"trace_id": "trace-2"},
            }
            return {"id": message["id"], "result": {"turnId": "turn-1"}}

        transport.responses["turn/start"] = start_turn
        transport.responses["turn/steer"] = steer_turn
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()
        stream = await thread.run("Summarize this repo.")
        steered = await stream.steer(
            "Add detail.",
            responsesapi_client_metadata={"trace_id": "trace-2"},
        )

        transport.push(
            {
                "method": "turn/started",
                "params": {"threadId": "thr-1", "turn": _turn_payload()},
            }
        )
        transport.push(
            {
                "method": "hook/started",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "run": _hook_run_payload(),
                },
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
                "method": "hook/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "run": _hook_run_payload(status="completed"),
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
            protocol.HookStartedNotificationModel,
            protocol.ItemAgentMessageDeltaNotification,
            protocol.ItemCompletedNotificationModel,
            protocol.HookCompletedNotificationModel,
            protocol.TurnCompletedNotificationModel,
        ]
        assert events[2].params.delta == "Repository summary"
        assert isinstance(events[3].params.item.root, protocol.AgentMessageThreadItem)
        assert steered.turn_id == "turn-1"
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


def test_async_turn_stream_ignores_unscoped_notifications_in_non_strict_mode() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_turn(message: JsonObject) -> JsonObject:
            transport.push(
                {
                    "method": "codex/event/mcp_startup_update",
                    "params": {
                        "id": "",
                        "conversationId": "thr-1",
                        "msg": {
                            "type": "mcp_startup_update",
                            "server": "shopify",
                            "status": {"state": "starting"},
                        },
                    },
                }
            )
            return {"id": message["id"], "result": {"turn": _turn_payload()}}

        transport.responses["turn/start"] = start_turn
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()
        stream = await thread.run("Summarize this repo.")
        transport.push(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-other",
                    "turnId": "turn-other",
                    "item": _agent_message_item("Ignore me"),
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
            protocol.ItemCompletedNotificationModel,
            protocol.TurnCompletedNotificationModel,
        ]
        assert stream.final_text == "Repository summary"
        assert stream.final_turn is not None
        assert stream.final_turn.status.root == "completed"

        await client.close()

    asyncio.run(scenario())


def test_async_client_strict_mode_rejects_unknown_notifications() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()

        def start_thread(message: JsonObject) -> JsonObject:
            transport.push(
                {
                    "method": "codex/event/mcp_startup_update",
                    "params": {
                        "id": "",
                        "conversationId": "thr-1",
                        "msg": {
                            "type": "mcp_startup_update",
                            "server": "shopify",
                            "status": {"state": "starting"},
                        },
                    },
                }
            )
            return {"id": message["id"], "result": {"thread": _thread_payload()}}

        transport.responses["thread/start"] = start_thread
        client = AsyncAppServerClient(
            transport,
            AppServerInitializeOptions(strict_protocol=True),
        )
        await client.start()

        with pytest.raises(
            AppServerProtocolError,
            match="Unsupported app-server notification method",
        ):
            await client.start_thread()

        await client.close()

    asyncio.run(scenario())


def test_async_client_accepts_generic_unknown_server_request_in_non_strict_mode() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        client = AsyncAppServerClient(transport)
        await client.start()

        seen: list[GenericServerRequest] = []

        def handle_custom_request(request: GenericServerRequest) -> JsonObject:
            seen.append(request)
            assert request.method == "custom/request"
            assert request.params == {"foo": "bar"}
            return {"ok": True}

        client.on_request("custom/request", handle_custom_request)

        transport.push(
            {
                "id": "req-1",
                "method": "custom/request",
                "params": {"foo": "bar"},
            }
        )

        response = await asyncio.to_thread(
            transport.wait_for_message, lambda message: message.get("id") == "req-1"
        )

        assert seen == [
            GenericServerRequest(id="req-1", method="custom/request", params={"foo": "bar"})
        ]
        assert response == {"id": "req-1", "result": {"ok": True}}

        await client.close()

    asyncio.run(scenario())


def test_async_client_returns_actionable_server_request_error_payload() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        client = AsyncAppServerClient(transport)
        await client.start()

        def handle_custom_request(request: GenericServerRequest) -> JsonObject:
            _ = request
            raise ValueError("boom")

        client.on_request("custom/request", handle_custom_request)

        transport.push(
            {
                "id": "req-1",
                "method": "custom/request",
                "params": {"foo": "bar"},
            }
        )

        await asyncio.to_thread(
            transport.wait_for_message,
            lambda message: message.get("id") == "req-1" and "error" in message,
        )

        error_response = next(
            message
            for message in transport.sent
            if message.get("id") == "req-1" and "error" in message
        )
        assert error_response == {
            "id": "req-1",
            "error": {
                "code": -32000,
                "message": "ValueError: boom",
                "data": {
                    "exceptionType": "ValueError",
                    "exceptionModule": "builtins",
                    "exceptionMessage": "boom",
                },
            },
        }

        await client.close()

    asyncio.run(scenario())


def test_async_client_close_surfaces_reader_failure() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        client = AsyncAppServerClient(transport)
        await client.start()

        transport.push({"unexpected": "message"})

        reader_task = client._session._reader_task
        assert reader_task is not None
        with suppress(AppServerProtocolError):
            await asyncio.wait_for(asyncio.shield(reader_task), timeout=1)

        with pytest.raises(AppServerProtocolError, match="Unsupported app-server message"):
            await client.close()

        assert transport.closed is True

    asyncio.run(scenario())


def test_async_thread_run_text_json_and_model_helpers() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_turn(message: JsonObject) -> JsonObject:
            return {"id": message["id"], "result": {"turn": _turn_payload()}}

        transport.responses["turn/start"] = start_turn
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
        await asyncio.to_thread(transport.wait_for_method, "turn/start", count=1)
        await push_turn_result("Async summary")
        assert await text_task == "Async summary"

        json_task = asyncio.create_task(thread.run_json("Return JSON"))
        await asyncio.to_thread(transport.wait_for_method, "turn/start", count=2)
        await push_turn_result('{"answer":"async structured summary"}')
        assert await json_task == {"answer": "async structured summary"}

        model_task = asyncio.create_task(thread.run_model("Return JSON", SummaryModel))
        turn_start_request = await asyncio.to_thread(
            transport.wait_for_method, "turn/start", count=3
        )
        assert turn_start_request["params"]["outputSchema"] == SummaryModel.model_json_schema()
        await push_turn_result('{"answer":"async model summary"}')
        assert await model_task == SummaryModel(answer="async model summary")

        await client.close()

    asyncio.run(scenario())


def test_async_thread_run_model_rejects_conflicting_output_schema() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()

        with pytest.raises(
            ValueError,
            match="AppServerThread.run_model\\(\\) received both model_type",
        ):
            await thread.run_model(
                "Return JSON",
                SummaryModel,
                AppServerTurnOptions(output_schema={"type": "object"}),
            )

        await client.close()

    asyncio.run(scenario())


def test_async_thread_run_helpers_raise_for_failed_terminal_turn() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        transport.responses["turn/start"] = {"turn": _turn_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()

        text_task = asyncio.create_task(thread.run_text("Summarize this repo."))
        await asyncio.to_thread(transport.wait_for_method, "turn/start")
        transport.push(
            {
                "method": "turn/completed",
                "params": {
                    "threadId": "thr-1",
                    "turn": _turn_payload(
                        status="failed",
                    )
                    | {
                        "error": {
                            "message": "request failed",
                            "codexErrorInfo": None,
                            "additionalDetails": None,
                        }
                    },
                },
            }
        )

        with pytest.raises(AppServerTurnError, match="request failed"):
            await text_task

        await client.close()

    asyncio.run(scenario())


def test_async_thread_review_uses_protocol_delivery_type() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_review(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "threadId": "thr-1",
                "target": {"type": "commit", "sha": "deadbeef", "title": "Review this commit"},
                "delivery": "detached",
            }
            return {
                "id": message["id"],
                "result": {
                    "turn": _turn_payload(),
                    "reviewThreadId": "thr-review-1",
                },
            }

        transport.responses["review/start"] = start_review
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()
        stream = await thread.review(
            target=protocol.CommitReviewTarget(
                type="commit",
                sha="deadbeef",
                title="Review this commit",
            ),
            delivery="detached",
        )

        assert stream.thread_id == "thr-review-1"
        assert stream.turn_id == "turn-1"
        await stream.close()
        await client.close()

    asyncio.run(scenario())


def test_async_thread_review_stream_does_not_buffer_unscoped_notifications() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def start_review(message: JsonObject) -> JsonObject:
            transport.push(
                {
                    "method": "turn/completed",
                    "params": {"threadId": "thr-unrelated", "turn": _turn_payload("turn-other")},
                }
            )
            return {
                "id": message["id"],
                "result": {
                    "turn": _turn_payload(),
                    "reviewThreadId": "thr-review-1",
                },
            }

        transport.responses["review/start"] = start_review
        client = AsyncAppServerClient(transport)
        await client.start()

        thread = await client.start_thread()
        stream = await thread.review(
            target=protocol.CommitReviewTarget(
                type="commit",
                sha="deadbeef",
                title="Review this commit",
            ),
            delivery="detached",
        )

        transport.push(
            {
                "method": "turn/completed",
                "params": {"threadId": "thr-review-1", "turn": _turn_payload()},
            }
        )

        event = await stream.__anext__()

        assert isinstance(event, protocol.TurnCompletedNotificationModel)
        assert event.params.threadId == "thr-review-1"

        with pytest.raises(StopAsyncIteration):
            await stream.__anext__()

        await client.close()

    asyncio.run(scenario())


def test_async_client_exposes_public_thread_operations() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}

        def read_thread(message: JsonObject) -> JsonObject:
            if message["params"] == {"threadId": "thr-1", "includeTurns": False}:
                return {
                    "id": message["id"],
                    "result": {"thread": {**_thread_payload(), "name": "Refreshed thread"}},
                }
            assert message["params"] == {"threadId": "thr-1", "includeTurns": True}
            return {
                "id": message["id"],
                "result": {"thread": {**_thread_payload(), "name": "Read thread"}},
            }

        def list_threads(message: JsonObject) -> JsonObject:
            if message["params"] == {"limit": 2}:
                return {
                    "id": message["id"],
                    "result": {
                        "data": [_thread_payload("thr-1"), _thread_payload("thr-2")],
                        "nextCursor": None,
                    },
                }
            assert message["params"] == {"cursor": "cursor-1", "limit": 1}
            return {
                "id": message["id"],
                "result": {
                    "data": [_thread_payload("thr-3")],
                    "nextCursor": "cursor-2",
                },
            }

        def list_loaded_threads(message: JsonObject) -> JsonObject:
            assert message["params"] == {}
            return {"id": message["id"], "result": {"data": ["thr-1", "thr-2"]}}

        def fork_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1", "model": "gpt-fork"}
            return {"id": message["id"], "result": {"thread": _thread_payload("thr-fork")}}

        def archive_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1"}
            return {"id": message["id"], "result": {}}

        def unarchive_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1"}
            return {
                "id": message["id"],
                "result": {"thread": {**_thread_payload(), "name": "Unarchived thread"}},
            }

        def rollback_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1", "numTurns": 2}
            return {
                "id": message["id"],
                "result": {"thread": {**_thread_payload(), "name": "Rolled back thread"}},
            }

        def compact_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1"}
            return {"id": message["id"], "result": {}}

        def set_thread_name(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1", "name": "Renamed thread"}
            return {"id": message["id"], "result": {}}

        def unsubscribe_thread(message: JsonObject) -> JsonObject:
            assert message["params"] == {"threadId": "thr-1"}
            return {"id": message["id"], "result": {}}

        transport.responses["thread/read"] = read_thread
        transport.responses["thread/list"] = list_threads
        transport.responses["thread/loaded/list"] = list_loaded_threads
        transport.responses["thread/fork"] = fork_thread
        transport.responses["thread/archive"] = archive_thread
        transport.responses["thread/unarchive"] = unarchive_thread
        transport.responses["thread/rollback"] = rollback_thread
        transport.responses["thread/compact/start"] = compact_thread
        transport.responses["thread/name/set"] = set_thread_name
        transport.responses["thread/unsubscribe"] = unsubscribe_thread

        client = AsyncAppServerClient(transport)
        await client.start()
        thread = await client.start_thread()

        refreshed = await thread.refresh()
        read = await client.read_thread("thr-1", include_turns=True)
        threads = await client.list_threads(AppServerThreadListOptions(limit=2))
        page = await client.list_threads_page(
            AppServerThreadListOptions(cursor="cursor-1", limit=1)
        )
        loaded_ids = await client.loaded_thread_ids()
        forked = await thread.fork(AppServerThreadForkOptions(model="gpt-fork"))
        archived = await thread.archive()
        assert thread.snapshot.name == "Refreshed thread"
        unarchived = await thread.unarchive()
        assert thread.snapshot.name == "Unarchived thread"
        rolled_back = await thread.rollback(2)
        assert thread.snapshot.name == "Rolled back thread"
        compacted = await thread.compact()
        renamed = await thread.set_name("Renamed thread")
        unsubscribed = await thread.unsubscribe()

        assert refreshed.name == "Refreshed thread"
        assert thread.snapshot.name == "Rolled back thread"
        assert read.name == "Read thread"
        assert [item.id for item in threads] == ["thr-1", "thr-2"]
        assert [item.id for item in page.data] == ["thr-3"]
        assert page.next_cursor == "cursor-2"
        assert loaded_ids == ["thr-1", "thr-2"]
        assert forked.id == "thr-fork"
        assert archived == EmptyResult()
        assert unarchived.name == "Unarchived thread"
        assert rolled_back.name == "Rolled back thread"
        assert compacted == EmptyResult()
        assert renamed == EmptyResult()
        assert unsubscribed == EmptyResult()

        await client.close()

    asyncio.run(scenario())


def test_async_client_exposes_typed_rpc_domain_clients() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()

        def list_models(message: JsonObject) -> JsonObject:
            assert message["params"] == {"includeHidden": False, "limit": 20}
            return {"id": message["id"], "result": _model_list_payload()}

        def list_apps(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "cursor": "cursor-1",
                "forceRefetch": True,
                "limit": 10,
                "threadId": "thr-1",
            }
            return {
                "id": message["id"],
                "result": {
                    "data": [
                        {
                            "id": "demo-app",
                            "name": "Demo App",
                            "description": "Example connector",
                            "logoUrl": "https://example.com/logo.png",
                            "logoUrlDark": None,
                            "distributionChannel": None,
                            "branding": None,
                            "appMetadata": None,
                            "labels": None,
                            "installUrl": "https://example.com/apps/demo-app",
                            "isAccessible": True,
                            "isEnabled": True,
                        }
                    ],
                    "nextCursor": None,
                },
            }

        def list_skills(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "cwds": ["/repo"],
                "forceReload": True,
                "perCwdExtraUserRoots": [
                    {"cwd": "/repo", "extraUserRoots": ["/shared-skills"]},
                ],
            }
            return {
                "id": message["id"],
                "result": {
                    "data": [
                        {
                            "cwd": "/repo",
                            "skills": [
                                {
                                    "name": "skill-creator",
                                    "description": "Create a skill",
                                    "enabled": True,
                                    "interface": {
                                        "displayName": "Skill Creator",
                                        "shortDescription": "Create or update skills",
                                        "iconSmall": None,
                                        "iconLarge": None,
                                        "brandColor": None,
                                        "defaultPrompt": None,
                                    },
                                    "path": "/repo/.codex/skills/skill-creator/SKILL.md",
                                    "shortDescription": "Create or update skills",
                                    "scope": "repo",
                                }
                            ],
                            "errors": [],
                        }
                    ]
                },
            }

        def write_skill_config(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "path": "/repo/.codex/skills/skill-creator/SKILL.md",
                "enabled": False,
            }
            return {"id": message["id"], "result": {"effectiveEnabled": False}}

        def account_read(message: JsonObject) -> JsonObject:
            assert message["params"] == {"refreshToken": True}
            return {
                "id": message["id"],
                "result": {
                    "account": {
                        "type": "chatgpt",
                        "email": "user@example.com",
                        "planType": "pro",
                    },
                    "requiresOpenaiAuth": True,
                },
            }

        login_call = 0

        def login_account(message: JsonObject) -> JsonObject:
            nonlocal login_call
            login_call += 1
            if login_call == 1:
                assert message["params"] == {"type": "apiKey", "apiKey": "sk-test"}
                return {"id": message["id"], "result": {"type": "apiKey"}}
            if login_call == 2:
                assert message["params"] == {"type": "chatgpt"}
                return {
                    "id": message["id"],
                    "result": {
                        "type": "chatgpt",
                        "authUrl": "https://example.com/login",
                        "loginId": "login-1",
                    },
                }
            assert message["params"] == {
                "type": "chatgptAuthTokens",
                "accessToken": "access-token",
                "chatgptAccountId": "acct-1",
                "chatgptPlanType": "enterprise",
            }
            return {"id": message["id"], "result": {"type": "chatgptAuthTokens"}}

        def cancel_login(message: JsonObject) -> JsonObject:
            assert message["params"] == {"loginId": "login-1"}
            return {"id": message["id"], "result": {"status": "canceled"}}

        def account_rate_limits(message: JsonObject) -> JsonObject:
            assert "params" not in message
            snapshot = {
                "limitId": "codex",
                "limitName": None,
                "planType": "pro",
                "primary": {
                    "usedPercent": 25,
                    "windowDurationMins": 15,
                    "resetsAt": 1730947200,
                },
                "secondary": None,
                "credits": None,
            }
            return {
                "id": message["id"],
                "result": {
                    "rateLimits": snapshot,
                    "rateLimitsByLimitId": {"codex": snapshot},
                },
            }

        def config_read(message: JsonObject) -> JsonObject:
            assert message["params"] == {"cwd": "/repo", "includeLayers": True}
            return {
                "id": message["id"],
                "result": {
                    "config": {
                        "model": "gpt-5.4",
                        "approval_policy": "on-request",
                        "sandbox_mode": "workspace-write",
                    },
                    "layers": [
                        {
                            "config": {"model": "gpt-5.4"},
                            "disabledReason": None,
                            "name": {"type": "user"},
                            "version": "v1",
                        }
                    ],
                    "origins": {"model": {"name": {"type": "user"}, "version": "v1"}},
                },
            }

        def write_value(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "keyPath": "model",
                "value": "gpt-5.4",
                "mergeStrategy": "replace",
                "expectedVersion": "v1",
            }
            return {
                "id": message["id"],
                "result": {
                    "filePath": "/home/user/.codex/config.toml",
                    "overriddenMetadata": None,
                    "status": "ok",
                    "version": "v2",
                },
            }

        def batch_write(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "edits": [
                    {
                        "keyPath": "apps.demo.enabled",
                        "mergeStrategy": "upsert",
                        "value": True,
                    }
                ],
                "filePath": "/home/user/.codex/config.toml",
            }
            return {
                "id": message["id"],
                "result": {
                    "filePath": "/home/user/.codex/config.toml",
                    "overriddenMetadata": None,
                    "status": "ok",
                    "version": "v3",
                },
            }

        def read_requirements(message: JsonObject) -> JsonObject:
            assert "params" not in message
            return {
                "id": message["id"],
                "result": {
                    "requirements": {
                        "allowedApprovalPolicies": ["on-request", "never"],
                        "allowedApprovalsReviewers": ["user"],
                        "allowedSandboxModes": ["read-only", "workspace-write"],
                        "allowedWebSearchModes": ["disabled", "live"],
                        "enforceResidency": "us",
                        "featureRequirements": {"personality": {"required": True}},
                        "network": {
                            "enabled": True,
                            "allowedDomains": ["api.openai.com"],
                            "deniedDomains": ["example.invalid"],
                            "managedAllowedDomainsOnly": True,
                        },
                    }
                },
            }

        def reload_mcp_servers(message: JsonObject) -> JsonObject:
            assert "params" not in message
            return {"id": message["id"], "result": {}}

        def oauth_login(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "name": "github",
                "scopes": ["repo"],
                "timeoutSecs": 30,
            }
            return {
                "id": message["id"],
                "result": {"authorizationUrl": "https://example.com/oauth"},
            }

        def list_mcp_status(message: JsonObject) -> JsonObject:
            assert message["params"] == {"cursor": "cursor-2", "limit": 5}
            return {
                "id": message["id"],
                "result": {
                    "data": [
                        {
                            "name": "github",
                            "authStatus": "oAuth",
                            "tools": {
                                "repo_status": {
                                    "_meta": {"origin": "pytest"},
                                    "annotations": {"readOnlyHint": True},
                                    "description": "Read repository status",
                                    "inputSchema": {"type": "object", "properties": {}},
                                    "name": "repo_status",
                                    "outputSchema": {"type": "object"},
                                    "title": "Repo status",
                                }
                            },
                            "resources": [
                                {
                                    "_meta": {"origin": "pytest"},
                                    "description": "Repository README",
                                    "mimeType": "text/markdown",
                                    "name": "readme",
                                    "size": 12,
                                    "title": "README",
                                    "uri": "file:///repo/README.md",
                                }
                            ],
                            "resourceTemplates": [
                                {
                                    "description": "Repository files",
                                    "mimeType": "text/plain",
                                    "name": "repo_files",
                                    "title": "Repository files",
                                    "uriTemplate": "file:///repo/{path}",
                                }
                            ],
                        }
                    ],
                    "nextCursor": None,
                },
            }

        def upload_feedback(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "classification": "bug",
                "extraLogFiles": ["/tmp/app.log"],
                "includeLogs": True,
                "reason": "Needs follow-up",
                "threadId": "thr-1",
            }
            return {"id": message["id"], "result": {"threadId": "thr-feedback"}}

        def command_exec(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "command": ["git", "status"],
                "cwd": "/repo",
                "sandboxPolicy": {"type": "workspaceWrite", "networkAccess": True},
                "timeoutMs": 5000,
            }
            return {
                "id": message["id"],
                "result": {"exitCode": 0, "stdout": "clean\n", "stderr": ""},
            }

        def detect_external_agent_config(message: JsonObject) -> JsonObject:
            assert message["params"] == {"cwds": ["/repo"], "includeHome": True}
            return {
                "id": message["id"],
                "result": {
                    "items": [
                        {
                            "itemType": "AGENTS_MD",
                            "description": "Import CLAUDE.md",
                            "cwd": "/repo",
                        }
                    ]
                },
            }

        def import_external_agent_config(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "migrationItems": [
                    {
                        "itemType": "AGENTS_MD",
                        "description": "Import CLAUDE.md",
                        "cwd": "/repo",
                    }
                ]
            }
            return {"id": message["id"], "result": {}}

        def windows_sandbox_setup_start(message: JsonObject) -> JsonObject:
            assert message["params"] == {"mode": "elevated", "cwd": "C:/repo"}
            return {"id": message["id"], "result": {"started": True}}

        transport.responses["model/list"] = list_models
        transport.responses["app/list"] = list_apps
        transport.responses["skills/list"] = list_skills
        transport.responses["skills/config/write"] = write_skill_config
        transport.responses["account/read"] = account_read
        transport.responses["account/login/start"] = login_account
        transport.responses["account/login/cancel"] = cancel_login
        transport.responses["account/logout"] = {}
        transport.responses["account/rateLimits/read"] = account_rate_limits
        transport.responses["config/read"] = config_read
        transport.responses["config/value/write"] = write_value
        transport.responses["config/batchWrite"] = batch_write
        transport.responses["configRequirements/read"] = read_requirements
        transport.responses["config/mcpServer/reload"] = reload_mcp_servers
        transport.responses["mcpServer/oauth/login"] = oauth_login
        transport.responses["mcpServerStatus/list"] = list_mcp_status
        transport.responses["feedback/upload"] = upload_feedback
        transport.responses["command/exec"] = command_exec
        transport.responses["externalAgentConfig/detect"] = detect_external_agent_config
        transport.responses["externalAgentConfig/import"] = import_external_agent_config
        transport.responses["windowsSandbox/setupStart"] = windows_sandbox_setup_start
        client = AsyncAppServerClient(transport)
        await client.start()

        models = await client.models.list(limit=20, include_hidden=False)
        model_page = await client.models.list_page(limit=20, include_hidden=False)
        apps = await client.apps.list(
            cursor="cursor-1",
            force_refetch=True,
            limit=10,
            thread_id="thr-1",
        )
        app_page = await client.apps.list_page(
            cursor="cursor-1",
            force_refetch=True,
            limit=10,
            thread_id="thr-1",
        )
        skills = await client.skills.list(
            cwds=["/repo"],
            force_reload=True,
            per_cwd_extra_user_roots=[
                protocol.SkillsListExtraRootsForCwd(
                    cwd="/repo",
                    extraUserRoots=["/shared-skills"],
                )
            ],
        )
        skills_result = await client.skills.list_page(
            cwds=["/repo"],
            force_reload=True,
            per_cwd_extra_user_roots=[
                protocol.SkillsListExtraRootsForCwd(
                    cwd="/repo",
                    extraUserRoots=["/shared-skills"],
                )
            ],
        )
        skill_config = await client.skills.write_config(
            path="/repo/.codex/skills/skill-creator/SKILL.md",
            enabled=False,
        )
        account = await client.account.read(refresh_token=True)
        api_key_login = await client.account.login_api_key(api_key="sk-test")
        chatgpt_login = await client.account.login_chatgpt()
        chatgpt_tokens_login = await client.account.login_chatgpt_tokens(
            access_token="access-token",
            chatgpt_account_id="acct-1",
            chatgpt_plan_type=protocol.PlanType("enterprise"),
        )
        canceled_login = await client.account.cancel_login(login_id="login-1")
        logout_result = await client.account.logout()
        rate_limits = await client.account.read_rate_limits()
        config = await client.config.read(cwd="/repo", include_layers=True)
        write_result = await client.config.write_value(
            key_path="model",
            value="gpt-5.4",
            merge_strategy="replace",
            expected_version="v1",
        )
        batch_result = await client.config.batch_write(
            edits=[
                protocol.ConfigEdit(
                    keyPath="apps.demo.enabled",
                    mergeStrategy="upsert",
                    value=True,
                )
            ],
            file_path="/home/user/.codex/config.toml",
        )
        requirements = await client.config.read_requirements()
        reload_result = await client.config.reload_mcp_servers()
        oauth_result = await client.mcp_servers.oauth_login(
            name="github",
            scopes=["repo"],
            timeout_seconds=30,
        )
        mcp_status = await client.mcp_servers.list(cursor="cursor-2", limit=5)
        mcp_status_page = await client.mcp_servers.list_page(cursor="cursor-2", limit=5)
        mcp_status_alias = await client.mcp_servers.list_status(cursor="cursor-2", limit=5)
        mcp_status_page_alias = await client.mcp_servers.list_status_page(
            cursor="cursor-2",
            limit=5,
        )
        feedback = await client.feedback.upload(
            classification="bug",
            include_logs=True,
            extra_log_files=["/tmp/app.log"],
            reason="Needs follow-up",
            thread_id="thr-1",
        )
        command = await client.command.execute(
            command=["git", "status"],
            cwd="/repo",
            sandbox_policy=protocol.WorkspaceWriteSandboxPolicy(
                type="workspaceWrite",
                networkAccess=True,
            ),
            timeout_ms=5000,
        )
        detected = await client.external_agent_config.detect(cwds=["/repo"], include_home=True)
        import_result = await client.external_agent_config.import_items(
            migration_items=[
                protocol.ExternalAgentConfigMigrationItem(
                    itemType="AGENTS_MD",
                    description="Import CLAUDE.md",
                    cwd="/repo",
                )
            ]
        )
        windows_setup = await client.windows_sandbox.setup_start(mode="elevated", cwd="C:/repo")

        assert models[0].display_name == "GPT-5.4"
        assert model_page.data[0].display_name == "GPT-5.4"
        assert apps[0].id == "demo-app"
        assert app_page.data[0].id == "demo-app"
        assert skills[0].cwd == "/repo"
        assert skills[0].skills[0].interface is not None
        assert skills[0].skills[0].interface.display_name == "Skill Creator"
        assert skills[0].skills[0].short_description == "Create or update skills"
        assert skills_result.data[0].cwd == "/repo"
        assert skill_config.effective_enabled is False
        assert account.account is not None
        assert account.account.type == "chatgpt"
        assert api_key_login.type == "apiKey"
        assert chatgpt_login.login_id == "login-1"
        assert chatgpt_tokens_login.type == "chatgptAuthTokens"
        assert canceled_login.status == "canceled"
        assert logout_result == EmptyResult()
        assert rate_limits.rate_limits.limitId == "codex"
        assert config.config.model == "gpt-5.4"
        assert write_result.version == "v2"
        assert batch_result.version == "v3"
        assert requirements.requirements is not None
        assert requirements.requirements.allowed_sandbox_modes is not None
        assert [mode.root for mode in requirements.requirements.allowed_sandbox_modes] == [
            "read-only",
            "workspace-write",
        ]
        assert requirements.requirements.allowed_approvals_reviewers is not None
        assert [
            reviewer.root for reviewer in requirements.requirements.allowed_approvals_reviewers
        ] == ["user"]
        assert requirements.requirements.allowed_web_search_modes is not None
        assert [mode.root for mode in requirements.requirements.allowed_web_search_modes] == [
            "disabled",
            "live",
        ]
        assert requirements.requirements.enforce_residency is not None
        assert requirements.requirements.enforce_residency.root == "us"
        assert requirements.requirements.feature_requirements == {"personality": {"required": True}}
        assert requirements.requirements.network is not None
        assert requirements.requirements.network.enabled is True
        assert requirements.requirements.network.allowedDomains == ["api.openai.com"]
        assert requirements.requirements.network.deniedDomains == ["example.invalid"]
        assert requirements.requirements.network.managedAllowedDomainsOnly is True
        assert reload_result == EmptyResult()
        assert oauth_result.authorization_url == "https://example.com/oauth"
        assert mcp_status[0].name == "github"
        assert isinstance(mcp_status[0].auth_status, protocol.McpAuthStatus)
        assert mcp_status[0].auth_status.root == "oAuth"
        assert isinstance(mcp_status[0].tools["repo_status"], protocol.Tool)
        assert mcp_status[0].tools["repo_status"].field_meta == {"origin": "pytest"}
        assert mcp_status[0].tools["repo_status"].inputSchema == {
            "type": "object",
            "properties": {},
        }
        assert mcp_status[0].tools["repo_status"].outputSchema == {"type": "object"}
        assert isinstance(mcp_status[0].resources[0], protocol.Resource)
        assert mcp_status[0].resources[0].field_meta == {"origin": "pytest"}
        assert mcp_status[0].resources[0].mimeType == "text/markdown"
        assert mcp_status[0].resources[0].uri == "file:///repo/README.md"
        assert isinstance(mcp_status[0].resource_templates[0], protocol.ResourceTemplate)
        assert mcp_status[0].resource_templates[0].uriTemplate == "file:///repo/{path}"
        assert mcp_status_page.data[0].name == "github"
        assert mcp_status_alias[0].name == "github"
        assert mcp_status_page_alias.data[0].name == "github"
        assert feedback.thread_id == "thr-feedback"
        assert command.exit_code == 0
        assert detected.items[0].itemType.root == "AGENTS_MD"
        assert import_result == EmptyResult()
        assert windows_setup.started is True

        await client.close()

    asyncio.run(scenario())


def test_async_rpc_supports_raw_and_typed_calls_for_unsupported_methods() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["experimentalFeature/list"] = {"data": [], "nextCursor": None}
        client = AsyncAppServerClient(transport)
        await client.start()

        raw_result = await client.rpc.request("experimentalFeature/list", {"limit": 20})
        typed_result = await client.rpc.request_typed(
            "experimentalFeature/list",
            {"limit": 20},
            ExperimentalFeatureListResponse,
        )

        request = next(
            message
            for message in transport.sent
            if message.get("method") == "experimentalFeature/list"
        )
        assert request["params"] == {"limit": 20}
        assert raw_result == {"data": [], "nextCursor": None}
        assert typed_result == ExperimentalFeatureListResponse(data=[], nextCursor=None)

        with pytest.raises(ValidationError, match="unsupported_flag"):
            AppServerTurnOptions(unsupported_flag=True)  # type: ignore[call-arg]

        await client.close()

    asyncio.run(scenario())


def test_async_command_client_exposes_0_122_exec_controls() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()

        def command_exec(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "command": ["bash"],
                "cwd": "/repo",
                "disableTimeout": True,
                "env": {"TERM": "xterm-256color"},
                "outputBytesCap": 4096,
                "processId": "proc-1",
                "size": {"cols": 80, "rows": 24},
                "streamStdin": True,
                "streamStdoutStderr": True,
                "tty": True,
            }
            return {
                "id": message["id"],
                "result": {"exitCode": 0, "stdout": "", "stderr": ""},
            }

        def command_write(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "processId": "proc-1",
                "deltaBase64": "aGVsbG8K",
                "closeStdin": True,
            }
            return {"id": message["id"], "result": {}}

        def command_resize(message: JsonObject) -> JsonObject:
            assert message["params"] == {
                "processId": "proc-1",
                "size": {"cols": 100, "rows": 30},
            }
            return {"id": message["id"], "result": {}}

        def command_terminate(message: JsonObject) -> JsonObject:
            assert message["params"] == {"processId": "proc-1"}
            return {"id": message["id"], "result": {}}

        transport.responses["command/exec"] = command_exec
        transport.responses["command/exec/write"] = command_write
        transport.responses["command/exec/resize"] = command_resize
        transport.responses["command/exec/terminate"] = command_terminate
        client = AsyncAppServerClient(transport)
        await client.start()

        result = await client.command.execute(
            command=["bash"],
            cwd="/repo",
            disable_timeout=True,
            env={"TERM": "xterm-256color"},
            output_bytes_cap=4096,
            process_id="proc-1",
            size=protocol.CommandExecTerminalSize(cols=80, rows=24),
            stream_stdin=True,
            stream_stdout_stderr=True,
            tty=True,
        )
        wrote = await client.command.write(
            process_id="proc-1",
            delta_base64="aGVsbG8K",
            close_stdin=True,
        )
        resized = await client.command.resize(
            process_id="proc-1",
            size=protocol.CommandExecTerminalSize(cols=100, rows=30),
        )
        terminated = await client.command.terminate(process_id="proc-1")

        assert result.exit_code == 0
        assert wrote == EmptyResult()
        assert resized == EmptyResult()
        assert terminated == EmptyResult()

        await client.close()

    asyncio.run(scenario())


def test_async_rpc_typed_result_validation_raises_protocol_error() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["experimentalFeature/list"] = {
            "data": {"bad": True},
            "nextCursor": None,
        }
        client = AsyncAppServerClient(transport)
        await client.start()

        with pytest.raises(
            AppServerProtocolError,
            match="Failed to parse app-server result for app-server method 'experimentalFeature/list'",
        ):
            await client.rpc.request_typed(
                "experimentalFeature/list",
                {"limit": 20},
                ExperimentalFeatureListResponse,
            )

        await client.close()

    asyncio.run(scenario())


def test_async_rpc_malformed_response_envelope_raises_protocol_error() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()

        def malformed_response(message: JsonObject) -> JsonObject:
            return {"id": message["id"], "oops": True}

        transport.responses["experimentalFeature/list"] = malformed_response
        client = AsyncAppServerClient(transport)
        await client.start()

        with pytest.raises(
            AppServerProtocolError,
            match="Malformed app-server response envelope",
        ):
            await client.rpc.request("experimentalFeature/list", {"limit": 20})

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

        response = await asyncio.to_thread(
            transport.wait_for_message, lambda message: message.get("id") == "req-1"
        )

        assert len(seen) == 1
        assert response == {"id": "req-1", "result": {"echo": "lookup_ticket"}}

        await client.close()

    asyncio.run(scenario())


def test_async_client_start_thread_registers_annotation_driven_dynamic_tools() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        raw_tool = protocol.DynamicToolSpec(
            name="raw_lookup",
            description="Raw tool.",
            inputSchema={"type": "object"},
        )

        @dynamic_tool
        def lookup_ticket(id: str) -> str:
            """Look up a support ticket by id."""
            return f"Ticket {id}"

        thread = await client.start_thread(
            AppServerThreadStartOptions(dynamic_tools=[raw_tool]),
            tools=[lookup_ticket],
        )

        request = transport.wait_for_method("thread/start")
        assert thread.id == "thr-1"
        assert [tool["name"] for tool in request["params"]["dynamicTools"]] == [
            "raw_lookup",
            "lookup_ticket",
        ]

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

        response = await asyncio.to_thread(
            transport.wait_for_message, lambda message: message.get("id") == "req-1"
        )
        assert response == {
            "id": "req-1",
            "result": {
                "contentItems": [{"type": "inputText", "text": "Ticket 123"}],
                "success": True,
            },
        }

        await client.close()

    asyncio.run(scenario())


def test_async_client_rejects_dynamic_tool_activation_after_manual_handler_registration() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        client.on_request(
            "item/tool/call",
            lambda request: {"ok": True},
            request_model=protocol.ItemToolCallRequest,
        )

        @dynamic_tool
        def lookup_ticket(id: str) -> str:
            """Look up a support ticket by id."""
            return id

        with pytest.raises(
            ValueError,
            match="Cannot activate annotation-driven dynamic tools after registering a manual",
        ):
            await client.start_thread(tools=[lookup_ticket])

        await client.close()

    asyncio.run(scenario())


def test_async_client_rejects_manual_dynamic_tool_handler_after_tool_activation() -> None:
    async def scenario() -> None:
        transport = ScriptedTransport()
        transport.responses["thread/start"] = {"thread": _thread_payload()}
        client = AsyncAppServerClient(transport)
        await client.start()

        @dynamic_tool
        def lookup_ticket(id: str) -> str:
            """Look up a support ticket by id."""
            return id

        await client.start_thread(tools=[lookup_ticket])

        with pytest.raises(
            ValueError,
            match="item/tool/call is reserved for annotation-driven dynamic tools",
        ):
            client.on_request(
                "item/tool/call",
                lambda request: {"ok": True},
                request_model=protocol.ItemToolCallRequest,
            )

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
            await asyncio.to_thread(transport.wait_for_method, "turn/start", count=1)
            push_turn_result("Sync summary")
            assert await text_future == "Sync summary"

            json_future = asyncio.create_task(asyncio.to_thread(thread.run_json, "Return JSON"))
            await asyncio.to_thread(transport.wait_for_method, "turn/start", count=2)
            push_turn_result('{"answer":"sync structured summary"}')
            assert await json_future == {"answer": "sync structured summary"}

            model_future = asyncio.create_task(
                asyncio.to_thread(thread.run_model, "Return JSON", SummaryModel)
            )
            await asyncio.to_thread(transport.wait_for_method, "turn/start", count=3)
            push_turn_result('{"answer":"sync model summary"}')
            assert await model_future == SummaryModel(answer="sync model summary")

        asyncio.run(run_in_threadpool())
    finally:
        client.close()


def test_sync_thread_run_model_rejects_conflicting_output_schema() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()

        with pytest.raises(
            ValueError,
            match="AppServerThread.run_model\\(\\) received both model_type",
        ):
            thread.run_model(
                "Return JSON",
                SummaryModel,
                AppServerTurnOptions(output_schema={"type": "object"}),
            )
    finally:
        client.close()


def test_sync_thread_run_helpers_raise_for_failed_terminal_turn() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    transport.responses["turn/start"] = {"turn": _turn_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()

        async def run_in_threadpool() -> None:
            text_future = asyncio.create_task(asyncio.to_thread(thread.run_text, "hello"))
            await asyncio.to_thread(transport.wait_for_method, "turn/start")
            transport.push(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thr-1",
                        "turn": _turn_payload(status="failed")
                        | {
                            "error": {
                                "message": "sync request failed",
                                "codexErrorInfo": None,
                                "additionalDetails": None,
                            }
                        },
                    },
                }
            )

            with pytest.raises(AppServerTurnError, match="sync request failed"):
                await text_future

        asyncio.run(run_in_threadpool())
    finally:
        client.close()


def test_sync_client_exposes_public_thread_operations() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}

    def read_thread(message: JsonObject) -> JsonObject:
        if message["params"] == {"threadId": "thr-1", "includeTurns": False}:
            return {
                "id": message["id"],
                "result": {"thread": {**_thread_payload(), "name": "Refreshed thread"}},
            }
        assert message["params"] == {"threadId": "thr-1", "includeTurns": True}
        return {
            "id": message["id"],
            "result": {"thread": {**_thread_payload(), "name": "Read thread"}},
        }

    def list_threads(message: JsonObject) -> JsonObject:
        if message["params"] == {"limit": 2}:
            return {
                "id": message["id"],
                "result": {
                    "data": [_thread_payload("thr-1"), _thread_payload("thr-2")],
                    "nextCursor": None,
                },
            }
        assert message["params"] == {"cursor": "cursor-1", "limit": 1}
        return {
            "id": message["id"],
            "result": {
                "data": [_thread_payload("thr-3")],
                "nextCursor": "cursor-2",
            },
        }

    def list_loaded_threads(message: JsonObject) -> JsonObject:
        assert message["params"] == {}
        return {"id": message["id"], "result": {"data": ["thr-1", "thr-2"]}}

    def fork_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1", "model": "gpt-fork"}
        return {"id": message["id"], "result": {"thread": _thread_payload("thr-fork")}}

    def archive_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1"}
        return {"id": message["id"], "result": {}}

    def unarchive_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1"}
        return {
            "id": message["id"],
            "result": {"thread": {**_thread_payload(), "name": "Unarchived thread"}},
        }

    def rollback_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1", "numTurns": 2}
        return {
            "id": message["id"],
            "result": {"thread": {**_thread_payload(), "name": "Rolled back thread"}},
        }

    def compact_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1"}
        return {"id": message["id"], "result": {}}

    def set_thread_name(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1", "name": "Renamed thread"}
        return {"id": message["id"], "result": {}}

    def unsubscribe_thread(message: JsonObject) -> JsonObject:
        assert message["params"] == {"threadId": "thr-1"}
        return {"id": message["id"], "result": {}}

    transport.responses["thread/read"] = read_thread
    transport.responses["thread/list"] = list_threads
    transport.responses["thread/loaded/list"] = list_loaded_threads
    transport.responses["thread/fork"] = fork_thread
    transport.responses["thread/archive"] = archive_thread
    transport.responses["thread/unarchive"] = unarchive_thread
    transport.responses["thread/rollback"] = rollback_thread
    transport.responses["thread/compact/start"] = compact_thread
    transport.responses["thread/name/set"] = set_thread_name
    transport.responses["thread/unsubscribe"] = unsubscribe_thread

    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        thread = client.start_thread()
        refreshed = thread.refresh()
        read = client.read_thread("thr-1", include_turns=True)
        threads = client.list_threads(AppServerThreadListOptions(limit=2))
        page = client.list_threads_page(AppServerThreadListOptions(cursor="cursor-1", limit=1))
        loaded_ids = client.loaded_thread_ids()
        forked = thread.fork(AppServerThreadForkOptions(model="gpt-fork"))
        archived = thread.archive()
        assert thread.snapshot.name == "Refreshed thread"
        unarchived = thread.unarchive()
        assert thread.snapshot.name == "Unarchived thread"
        rolled_back = thread.rollback(2)
        assert thread.snapshot.name == "Rolled back thread"
        compacted = thread.compact()
        renamed = thread.set_name("Renamed thread")
        unsubscribed = thread.unsubscribe()

        assert refreshed.name == "Refreshed thread"
        assert thread.snapshot.name == "Rolled back thread"
        assert read.name == "Read thread"
        assert [item.id for item in threads] == ["thr-1", "thr-2"]
        assert [item.id for item in page.data] == ["thr-3"]
        assert page.next_cursor == "cursor-2"
        assert loaded_ids == ["thr-1", "thr-2"]
        assert forked.id == "thr-fork"
        assert archived == EmptyResult()
        assert unarchived.name == "Unarchived thread"
        assert rolled_back.name == "Rolled back thread"
        assert compacted == EmptyResult()
        assert renamed == EmptyResult()
        assert unsubscribed == EmptyResult()
    finally:
        client.close()


def test_sync_client_exposes_typed_rpc_domain_clients_and_events() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()

    def list_models(message: JsonObject) -> JsonObject:
        assert message["params"] == {"limit": 5}
        return {"id": message["id"], "result": _model_list_payload()}

    def command_exec(message: JsonObject) -> JsonObject:
        assert message["params"] == {"command": ["git", "status"], "cwd": "/repo"}
        return {
            "id": message["id"],
            "result": {"exitCode": 0, "stdout": "clean\n", "stderr": ""},
        }

    def config_read(message: JsonObject) -> JsonObject:
        assert message["params"] == {"includeLayers": False}
        return {
            "id": message["id"],
            "result": {
                "config": {"model": "gpt-5.4"},
                "layers": None,
                "origins": {"model": {"name": {"type": "user"}, "version": "v1"}},
            },
        }

    def login_account(message: JsonObject) -> JsonObject:
        assert message["params"] == {
            "type": "chatgptAuthTokens",
            "accessToken": "access",
            "chatgptAccountId": "acct-1",
        }
        return {"id": message["id"], "result": {"type": "chatgptAuthTokens"}}

    transport.responses["model/list"] = list_models
    transport.responses["command/exec"] = command_exec
    transport.responses["config/read"] = config_read
    transport.responses["account/login/start"] = login_account
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    try:
        assert tuple(inspect.signature(client.models.list).parameters) == (
            "cursor",
            "include_hidden",
            "limit",
        )
        assert tuple(inspect.signature(client.command.execute).parameters) == (
            "command",
            "cwd",
            "disable_output_cap",
            "disable_timeout",
            "env",
            "output_bytes_cap",
            "process_id",
            "sandbox_policy",
            "size",
            "stream_stdin",
            "stream_stdout_stderr",
            "timeout_ms",
            "tty",
        )
        assert tuple(inspect.signature(client.command.write).parameters) == (
            "process_id",
            "close_stdin",
            "delta_base64",
        )
        assert tuple(inspect.signature(client.command.resize).parameters) == (
            "process_id",
            "size",
        )
        assert tuple(inspect.signature(client.command.terminate).parameters) == ("process_id",)
        assert tuple(inspect.signature(client.account.login_chatgpt_tokens).parameters) == (
            "access_token",
            "chatgpt_account_id",
            "chatgpt_plan_type",
        )
        models = client.models.list(limit=5)
        model_page = client.models.list_page(limit=5)
        command = client.command.execute(command=["git", "status"], cwd="/repo")
        config = client.config.read(include_layers=False)
        login = client.account.login_chatgpt_tokens(
            access_token="access",
            chatgpt_account_id="acct-1",
        )
        assert models[0].model == "gpt-5.4"
        assert model_page.data[0].model == "gpt-5.4"
        assert command.stdout == "clean\n"
        assert config.config.model == "gpt-5.4"
        assert login.type == "chatgptAuthTokens"

        subscription = client.events.subscribe({"codex/event/mcp_startup_update"})
        transport.push(
            {
                "method": "codex/event/mcp_startup_update",
                "params": {"conversationId": "thr-1", "msg": {"type": "mcp_startup_update"}},
            }
        )
        event = subscription.next()
        assert isinstance(event, GenericNotification)
        assert event.method == "codex/event/mcp_startup_update"
        subscription.close()
    finally:
        client.close()


def test_loop_thread_run_cancels_future_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeFuture:
        def __init__(self) -> None:
            self.cancelled = False

        def done(self) -> bool:
            return True

        def result(self, timeout: float | None = None) -> None:
            _ = timeout
            raise KeyboardInterrupt

        def cancel(self) -> bool:
            self.cancelled = True
            return True

    loop = _LoopThread()
    fake_future = FakeFuture()

    async def never() -> None:
        await asyncio.sleep(60)

    original_submit = loop._submit

    def fake_submit(coro: object) -> FakeFuture:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return fake_future

    monkeypatch.setattr(loop, "_submit", fake_submit)

    try:
        with pytest.raises(KeyboardInterrupt):
            loop.run(never())
        assert fake_future.cancelled is True
    finally:
        monkeypatch.setattr(loop, "_submit", original_submit)
        loop.close()


def test_sync_client_close_after_interrupted_run_closes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    transport.responses["thread/start"] = {"thread": _thread_payload()}
    transport.responses["turn/start"] = {"turn": _turn_payload()}
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)
    thread = client.start_thread()

    original_wait = loop._wait_for_future_result
    interrupted = False

    def interrupt_once(future: concurrent.futures.Future[object]) -> object:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        return original_wait(future)

    monkeypatch.setattr(loop, "_wait_for_future_result", interrupt_once)

    try:
        with pytest.raises(KeyboardInterrupt):
            thread.run_text("Summarize this repo.")
    finally:
        monkeypatch.setattr(loop, "_wait_for_future_result", original_wait)
        client.close()

    assert transport.closed is True


def test_sync_client_close_surfaces_reader_failure() -> None:
    loop = _LoopThread()
    transport = ScriptedTransport()
    async_client = AsyncAppServerClient(transport)
    loop.run(async_client.start())
    client = AppServerClient(async_client, loop)

    transport.push({"unexpected": "message"})

    async def wait_for_reader_failure() -> None:
        reader_task = async_client._session._reader_task
        assert reader_task is not None
        with suppress(AppServerProtocolError):
            await asyncio.wait_for(asyncio.shield(reader_task), timeout=1)

    loop.run(wait_for_reader_failure())

    with pytest.raises(AppServerProtocolError, match="Unsupported app-server message"):
        client.close()

    assert transport.closed is True
