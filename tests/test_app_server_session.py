from __future__ import annotations

import asyncio
import gc
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel, RootModel

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


def test_async_session_start_preserves_error_and_notes_cleanup_failure() -> None:
    async def scenario() -> None:
        class FailingCloseTransport(_FakeTransport):
            async def close(self) -> None:
                await super().close()
                raise RuntimeError("cleanup failed")

        transport = FailingCloseTransport()
        transport._fail_send_methods["initialized"] = RuntimeError("notify failed")
        session = _AsyncSession(transport)
        with pytest.raises(RuntimeError, match="notify failed") as exc_info:
            await session.start()

        assert exc_info.value.__notes__ == [
            "Cleanup after start failure also failed: RuntimeError('cleanup failed')"
        ]
        assert transport.closed
        await session.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


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


def test_async_session_request_serialization_failure_leaves_no_pending_request() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()

        with pytest.raises(TypeError, match="Request params must serialize to an object"):
            await session.request("invalid", RootModel[list[int]]([1]))

        assert session._pending == {}
        assert all(message.get("method") != "invalid" for message in transport.sent)
        assert await session.request("initialize") == {"userAgent": "test-client"}
        await session.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


@pytest.mark.parametrize("failure", ["send", "cancel_send", "cancel_wait"])
def test_async_session_request_abandonment_cleans_up_and_ignores_late_response(
    failure: str,
) -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()
        send_entered = asyncio.Event()
        original_send = transport.send

        async def interrupted_send(message: JsonObject) -> None:
            await original_send(message)
            if message.get("method") == "abandoned":
                send_entered.set()
                if failure == "send":
                    raise RuntimeError("send failed")
                if failure == "cancel_send":
                    await asyncio.Event().wait()

        transport.send = interrupted_send  # type: ignore[method-assign]
        request = asyncio.create_task(session.request("abandoned"))
        await send_entered.wait()
        request_id = transport.sent[-1]["id"]
        if failure == "send":
            with pytest.raises(RuntimeError, match="send failed"):
                await request
        else:
            future = session._pending[request_id]
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            assert future.cancelled()

        assert session._pending == {}
        transport.push({"id": request_id, "error": {"code": -1, "message": "late"}})
        assert await session.request("initialize") == {"userAgent": "test-client"}
        await session.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


@pytest.mark.parametrize("response_error", [False, True])
def test_async_session_request_cancellation_observes_racing_response(response_error: bool) -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()
        loop = asyncio.get_running_loop()
        unhandled: list[dict[str, Any]] = []
        loop.set_exception_handler(lambda loop, context: unhandled.append(context))

        async def respond_and_cancel(message: JsonObject) -> None:
            transport.sent.append(message)
            response: JsonObject = {"id": message["id"]}
            if response_error:
                response["error"] = {"code": -1, "message": "raced error"}
            else:
                response["result"] = {"ok": True}
            session._handle_response(response)
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            await asyncio.sleep(0)

        transport.send = respond_and_cancel  # type: ignore[method-assign]
        request = asyncio.create_task(session.request("race"))
        with pytest.raises(asyncio.CancelledError):
            await request
        assert session._pending == {}
        del request
        gc.collect()
        assert unhandled == []
        await session.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


def test_async_session_close_fails_and_removes_pending_request() -> None:
    async def scenario() -> None:
        session = _AsyncSession(_FakeTransport())
        await session.start()
        request = asyncio.create_task(session.request("pending"))
        await asyncio.sleep(0)
        assert len(session._pending) == 1

        await session.close()

        with pytest.raises(AppServerClosedError):
            await request
        assert session._pending == {}

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


def test_async_session_close_does_not_replay_reader_failure_reported_by_request() -> None:
    async def scenario() -> None:
        transport = _FakeTransport()
        session = _AsyncSession(transport)
        await session.start()
        request = asyncio.create_task(session.request("pending"))
        await asyncio.sleep(0)
        transport.push({"unexpected": "message"})

        with pytest.raises(AppServerProtocolError, match="Unsupported app-server message"):
            await request
        assert session._pending == {}
        await session.close()
        assert transport.closed

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


@pytest.mark.parametrize("blocked_stage", ["reader", "transport"])
@pytest.mark.parametrize("cancel_first_waiter", [False, True])
def test_async_session_close_joins_cleanup_and_survives_waiter_cancellation(
    blocked_stage: str, cancel_first_waiter: bool
) -> None:
    async def scenario() -> None:
        cleanup_entered = asyncio.Event()
        cleanup_release = asyncio.Event()

        class BlockingTransport(_FakeTransport):
            close_calls = 0

            async def receive(self) -> JsonObject | None:
                try:
                    return await super().receive()
                except asyncio.CancelledError:
                    if blocked_stage == "reader":
                        cleanup_entered.set()
                        await cleanup_release.wait()
                    raise

            async def close(self) -> None:
                self.close_calls += 1
                if blocked_stage == "transport":
                    cleanup_entered.set()
                    await cleanup_release.wait()
                await super().close()

        transport = BlockingTransport()
        session = _AsyncSession(transport)
        await session.start()
        subscription = session.subscribe_notifications()
        first_close = asyncio.create_task(session.close())
        await cleanup_entered.wait()
        second_close = asyncio.create_task(session.close())
        await asyncio.sleep(0)
        assert not first_close.done()
        assert not second_close.done()

        with pytest.raises(AppServerClosedError, match="closed"):
            await session.start()
        with pytest.raises(AppServerClosedError, match="closed"):
            await session.request("too-late")
        with pytest.raises(AppServerClosedError, match="closed"):
            await session.notify("too-late")

        if cancel_first_waiter:
            first_close.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first_close
            assert not second_close.done()

        cleanup_release.set()
        await second_close
        if not cancel_first_waiter:
            await first_close
        await session.close()

        assert transport.close_calls == 1
        assert transport.closed
        assert session._reader_task is None
        assert session._notification_sinks == []
        assert session._pending == {}
        with pytest.raises(StopAsyncIteration):
            await subscription.next()

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))


@pytest.mark.parametrize("cancel_waiter", [False, True])
def test_async_session_close_observes_cleanup_failure_and_does_not_replay_it(
    cancel_waiter: bool,
) -> None:
    async def scenario() -> None:
        cleanup_entered = asyncio.Event()
        cleanup_release = asyncio.Event()
        cleanup_finished = asyncio.Event()
        unhandled: list[dict[str, Any]] = []
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: unhandled.append(context)
        )

        class FailingCloseTransport(_FakeTransport):
            async def close(self) -> None:
                cleanup_entered.set()
                await cleanup_release.wait()
                await super().close()
                raise RuntimeError("close failed")

        transport = FailingCloseTransport()
        session = _AsyncSession(transport)
        await session.start()
        first_close = asyncio.create_task(session.close())
        await cleanup_entered.wait()
        assert session._close_task is not None
        session._close_task.add_done_callback(lambda task: cleanup_finished.set())

        if cancel_waiter:
            first_close.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first_close
        cleanup_release.set()
        if not cancel_waiter:
            with pytest.raises(RuntimeError, match="close failed"):
                await first_close
        await cleanup_finished.wait()
        await session.close()

        assert transport.closed
        assert session._reader_task is None
        del first_close, session
        await asyncio.sleep(0)
        gc.collect()
        assert unhandled == []

    asyncio.run(asyncio.wait_for(scenario(), timeout=1))
