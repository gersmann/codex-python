from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from codex.app_server._helpers import (
    Notification,
    RequestHandler,
    method_name,
    parse_result,
    request_id,
    serialize_value,
)
from codex.app_server.errors import (
    AppServerClosedError,
    AppServerProtocolError,
    AppServerRpcError,
)
from codex.app_server.models import InitializeResult
from codex.app_server.options import AppServerInitializeOptions
from codex.app_server.transports import AsyncMessageTransport, JsonObject
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class _NotificationSink:
    def __init__(self, methods: set[str] | None = None) -> None:
        self.methods = methods
        self.queue: asyncio.Queue[Notification | None] = asyncio.Queue()

    def matches(self, method: str) -> bool:
        return self.methods is None or method in self.methods


@dataclass(slots=True)
class _AsyncNotificationSubscription:
    queue: asyncio.Queue[Notification | None]
    close_callback: Callable[[], None]

    async def next(self) -> Notification:
        message = await self.queue.get()
        if message is None:
            raise StopAsyncIteration
        return message

    async def close(self) -> None:
        self.close_callback()
        await self.queue.put(None)


@dataclass(slots=True)
class _RegisteredHandler:
    handler: RequestHandler
    request_model: type[BaseModel] | None = None


class _AsyncSession:
    def __init__(
        self,
        transport: AsyncMessageTransport,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> None:
        self._transport = transport
        self._initialize_options = initialize_options or AppServerInitializeOptions()
        self._started = False
        self._closed = False
        self._next_request_id = 0
        self._pending: dict[int | str, asyncio.Future[object]] = {}
        self._request_handlers: dict[str, _RegisteredHandler] = {}
        self._notification_sinks: list[_NotificationSink] = []
        self._reader_task: asyncio.Task[None] | None = None
        self._initialize_result: InitializeResult | None = None

    async def start(self) -> InitializeResult:
        if self._started:
            if self._initialize_result is None:
                raise AppServerClosedError("app-server client initialization state is inconsistent")
            return self._initialize_result
        await self._transport.start()
        self._reader_task = asyncio.create_task(self._reader_loop())
        result = await self.request_typed(
            "initialize",
            self._initialize_options.to_params(),
            InitializeResult,
        )
        await self.notify("initialized", {})
        self._initialize_result = result
        self._started = True
        return result

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._fail_pending(AppServerClosedError("app-server client closed"))
        await self._transport.close()
        for sink in list(self._notification_sinks):
            await sink.queue.put(None)
        self._notification_sinks.clear()

    async def notify(
        self, method: str, params: BaseModel | Mapping[str, Any] | None = None
    ) -> None:
        await self._ensure_started_or_starting()
        message: JsonObject = {"method": method}
        if params is not None:
            serialized = serialize_value(params)
            if not isinstance(serialized, dict):
                raise TypeError(
                    f"Notification params must serialize to an object, got {type(serialized).__name__}"
                )
            message["params"] = cast(JsonObject, serialized)
        await self._transport.send(message)

    async def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, Any] | None = None,
    ) -> object:
        await self._ensure_started_or_starting()
        request_id_value = self._next_request_id
        self._next_request_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object] = loop.create_future()
        self._pending[request_id_value] = future
        message: JsonObject = {"id": request_id_value, "method": method}
        if params is not None:
            serialized = serialize_value(params)
            if not isinstance(serialized, dict):
                raise TypeError(
                    f"Request params must serialize to an object, got {type(serialized).__name__}"
                )
            message["params"] = cast(JsonObject, serialized)
        await self._transport.send(message)
        return await future

    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, Any] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        return cast(_ModelT, parse_result(await self.request(method, params), result_model))

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        self._request_handlers[method] = _RegisteredHandler(handler, request_model=request_model)

    def subscribe_notifications(
        self, methods: Collection[str] | None = None
    ) -> _AsyncNotificationSubscription:
        sink = _NotificationSink(None if methods is None else set(methods))
        self._notification_sinks.append(sink)
        return _AsyncNotificationSubscription(sink.queue, lambda: self._remove_sink(sink))

    async def _ensure_started_or_starting(self) -> None:
        if self._closed:
            raise AppServerClosedError("app-server client is closed")
        if self._reader_task is None:
            raise AppServerClosedError("app-server client is not started")

    async def _reader_loop(self) -> None:
        try:
            while True:
                message = await self._transport.receive()
                if message is None:
                    raise AppServerClosedError("app-server closed the transport")
                if "id" in message and "method" not in message:
                    self._handle_response(message)
                    continue
                if "id" in message and "method" in message:
                    await self._handle_server_request(message)
                    continue
                if "method" in message:
                    await self._broadcast_notification(message)
                    continue
                raise AppServerProtocolError(f"Unsupported app-server message: {message}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._fail_pending(exc)
            for sink in list(self._notification_sinks):
                await sink.queue.put(None)

    def _handle_response(self, message: JsonObject) -> None:
        pending_id = message.get("id")
        future = self._pending.pop(cast(int | str, pending_id), None)
        if future is None:
            return
        if "error" in message:
            parsed = protocol.JSONRPCError.model_validate(message)
            future.set_exception(
                AppServerRpcError(
                    parsed.error.code,
                    parsed.error.message,
                    parsed.error.data,
                )
            )
            return
        response = protocol.JSONRPCResponse.model_validate(message)
        future.set_result(response.result)

    async def _broadcast_notification(self, message: JsonObject) -> None:
        notification = protocol.ServerNotification.model_validate(message).root
        notification_method = method_name(notification)
        for sink in list(self._notification_sinks):
            if sink.matches(notification_method):
                await sink.queue.put(notification)

    async def _handle_server_request(self, message: JsonObject) -> None:
        request = protocol.ServerRequest.model_validate(message).root
        request_method = method_name(request)
        request_id_value = request_id(request)
        registered = self._request_handlers.get(request_method)
        if registered is None:
            await self._transport.send(
                {
                    "id": request_id_value,
                    "error": {
                        "code": -32601,
                        "message": f"No handler registered for app-server request {request_method}",
                    },
                }
            )
            return
        try:
            request_value: BaseModel = request
            if registered.request_model is not None:
                request_value = registered.request_model.model_validate(
                    request.model_dump(mode="json", by_alias=True)
                )
            result = registered.handler(request_value)
            if inspect.isawaitable(result):
                result = await cast(Awaitable[object], result)
            response_result = {} if result is None else serialize_value(result)
            await self._transport.send({"id": request_id_value, "result": response_result})
        except Exception as exc:
            await self._transport.send(
                {
                    "id": request_id_value,
                    "error": {
                        "code": -32000,
                        "message": str(exc),
                    },
                }
            )

    def _fail_pending(self, exc: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()

    def _remove_sink(self, sink: _NotificationSink) -> None:
        if sink in self._notification_sinks:
            self._notification_sinks.remove(sink)
