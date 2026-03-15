from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel

from codex.app_server._session import _AsyncSession, _jsonrpc_error_from_exception
from codex.app_server.errors import AppServerClosedError, AppServerProtocolError, AppServerRpcError
from codex.app_server.options import AppServerInitializeOptions

JsonObject = dict[str, Any]


class _FakeTransport:
    def __init__(self) -> None:
        self.sent: list[JsonObject] = []
        self.started = False
        self.closed = False
        self._incoming: asyncio.Queue[JsonObject | None] = asyncio.Queue()
        self._fail_send_methods: dict[str, Exception] = {}

    async def start(self) -> None:
        self.started = True

    async def send(self, message: JsonObject) -> None:
        method = message.get("method")
        if isinstance(method, str) and method in self._fail_send_methods:
            raise self._fail_send_methods[method]
        self.sent.append(message)
        if message.get("method") == "initialize" and "id" in message:
            self.push({"id": message["id"], "result": {"userAgent": "test-client"}})

    async def receive(self) -> JsonObject | None:
        return await self._incoming.get()

    async def close(self) -> None:
        self.closed = True
        self.push(None)

    def push(self, message: JsonObject | None) -> None:
        self._incoming.put_nowait(message)


def test_jsonrpc_error_from_exception_preserves_rpc_fields() -> None:
    error = _jsonrpc_error_from_exception(AppServerRpcError(123, "boom", {"detail": "bad"}))

    assert error == {"code": 123, "message": "boom", "data": {"detail": "bad"}}


def test_jsonrpc_error_from_exception_adds_exception_metadata() -> None:
    error = _jsonrpc_error_from_exception(ValueError("boom"))

    assert error == {
        "code": -32000,
        "message": "ValueError: boom",
        "data": {
            "exceptionType": "ValueError",
            "exceptionModule": "builtins",
            "exceptionMessage": "boom",
        },
    }


def test_async_session_broadcast_routes_only_matching_notifications() -> None:
    async def scenario() -> None:
        session = _AsyncSession(
            _FakeTransport(),
            AppServerInitializeOptions(strict_protocol=False),
        )
        matching = session.subscribe_notifications(
            ["custom/notify"],
            predicate=lambda notification: (
                isinstance(getattr(notification, "params", None), Mapping)
                and notification.params.get("threadId") == "thr-1"
            ),
        )
        non_matching = session.subscribe_notifications(["other/notify"])

        await session._broadcast_notification(
            {"method": "custom/notify", "params": {"threadId": "thr-1", "value": 1}}
        )

        event = await matching.next()
        assert event.method == "custom/notify"
        assert event.params == {"threadId": "thr-1", "value": 1}

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(non_matching.next(), timeout=0.01)

        await matching.close()
        await non_matching.close()

    asyncio.run(scenario())


def test_async_session_server_request_without_handler_returns_method_not_found() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport, AppServerInitializeOptions(strict_protocol=False))

        await session._handle_server_request(
            {"id": "req-1", "method": "custom/request", "params": {"ok": True}}
        )

        assert transport.sent == [
            {
                "id": "req-1",
                "error": {
                    "code": -32601,
                    "message": "No handler registered for app-server request custom/request",
                },
            }
        ]

    asyncio.run(scenario())


def test_async_session_server_request_handler_failure_returns_structured_error() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport, AppServerInitializeOptions(strict_protocol=False))
        session.on_request(
            "custom/request", lambda request: (_ for _ in ()).throw(ValueError("boom"))
        )

        await session._handle_server_request(
            {"id": "req-1", "method": "custom/request", "params": {"ok": True}}
        )

        assert transport.sent == [
            {
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
        ]

    asyncio.run(scenario())


def test_async_session_start_rejects_after_close() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)

        result = await session.start()
        assert result.user_agent == "test-client"

        await session.close()

        with pytest.raises(AppServerClosedError, match="closed"):
            await session.start()

    asyncio.run(scenario())


def test_async_session_start_closes_transport_when_initialize_result_is_malformed() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()

        async def malformed_initialize_send(message: JsonObject) -> None:
            transport.sent.append(message)
            if message.get("method") == "initialize" and "id" in message:
                transport.push({"id": message["id"], "result": {"wrong": True}})

        transport.send = malformed_initialize_send  # type: ignore[method-assign]
        session = _AsyncSession(transport)

        with pytest.raises(
            AppServerProtocolError,
            match="Failed to parse app-server result for app-server method 'initialize'",
        ):
            await session.start()

        assert transport.closed is True

    asyncio.run(scenario())


def test_async_session_start_closes_transport_when_initialized_notify_fails() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        transport._fail_send_methods["initialized"] = RuntimeError("notify boom")
        session = _AsyncSession(transport)

        with pytest.raises(RuntimeError, match="notify boom"):
            await session.start()

        assert transport.closed is True

    asyncio.run(scenario())


def test_async_session_subscription_close_discards_buffered_notifications() -> None:
    async def scenario() -> None:
        session = _AsyncSession(_FakeTransport(), AppServerInitializeOptions(strict_protocol=False))
        subscription = session.subscribe_notifications(["custom/notify"])

        await session._broadcast_notification({"method": "custom/notify", "params": {"value": 1}})
        await subscription.close()

        with pytest.raises(StopAsyncIteration):
            await subscription.next()

    asyncio.run(scenario())


def test_async_session_subscription_surfaces_reader_failure() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()
        subscription = session.subscribe_notifications()

        transport.push({"unexpected": "message"})

        with pytest.raises(AppServerProtocolError, match="Unsupported app-server message"):
            await subscription.next()

        with pytest.raises(AppServerProtocolError, match="Unsupported app-server message"):
            await session.close()

    asyncio.run(scenario())


def test_async_session_request_model_adaptation_wraps_protocol_errors() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()

        class _WrongRequest(BaseModel):
            id: str
            unexpected: str

        session.on_request("item/tool/call", lambda request: request, request_model=_WrongRequest)

        await session._handle_server_request(
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

        assert transport.sent[-1] == {
            "id": "req-1",
            "error": {
                "code": -32000,
                "message": "AppServerProtocolError: Failed to parse app-server request 'item/tool/call' as _WrongRequest",
                "data": {
                    "exceptionType": "AppServerProtocolError",
                    "exceptionModule": "codex.app_server.errors",
                    "exceptionMessage": "Failed to parse app-server request 'item/tool/call' as _WrongRequest",
                },
            },
        }

        await session.close()

    asyncio.run(scenario())
