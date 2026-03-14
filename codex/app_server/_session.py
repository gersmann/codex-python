from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ValidationError

from codex.app_server._payloads import serialize_value
from codex.app_server._protocol_helpers import (
    Notification,
    RequestHandler,
    method_name,
    parse_notification,
    parse_result,
    parse_server_request,
    request_id,
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
_RequestT = TypeVar("_RequestT", bound=BaseModel)
_NotificationPredicate = Callable[[Notification], bool]


class _NotificationSink:
    def __init__(
        self,
        methods: set[str] | None = None,
        predicate: _NotificationPredicate | None = None,
    ) -> None:
        self.methods = methods
        self.predicate = predicate
        self.queue: asyncio.Queue[Notification | None] = asyncio.Queue()

    def matches(self, method: str, notification: Notification) -> bool:
        if self.methods is not None and method not in self.methods:
            return False
        return self.predicate is None or self.predicate(notification)


@dataclass(slots=True)
class _AsyncNotificationSubscription:
    sink: _NotificationSink
    queue: asyncio.Queue[Notification | None]
    close_callback: Callable[[], None]

    async def next(self) -> Notification:
        message = await self.queue.get()
        if message is None:
            raise StopAsyncIteration
        return message

    async def close(self) -> None:
        self.close_callback()
        while not self.queue.empty():
            self.queue.get_nowait()
        await self.queue.put(None)

    def update_predicate(self, predicate: _NotificationPredicate | None) -> None:
        self.sink.predicate = predicate


@dataclass(slots=True)
class _RegisteredHandler:
    handler: RequestHandler[BaseModel]
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
        self._reader_error: Exception | None = None
        self._reader_error_reported = False
        self._strict_protocol = self._initialize_options.strict_protocol
        self._initialize_result: InitializeResult | None = None

    async def start(self) -> InitializeResult:
        if self._closed:
            raise AppServerClosedError("app-server client is closed")
        if self._started:
            if self._initialize_result is None:
                raise AppServerClosedError("app-server client initialization state is inconsistent")
            return self._initialize_result
        await self._transport.start()
        self._reader_task = asyncio.create_task(self._reader_loop())
        try:
            result = await self.request_typed(
                "initialize",
                self._initialize_options.to_params(),
                InitializeResult,
            )
            await self.notify("initialized", {})
        except Exception as exc:
            close_error = await self._close_for_start_failure()
            if close_error is not None and close_error is not exc:
                exc.add_note(f"Cleanup after start failure also failed: {close_error!r}")
            raise
        self._initialize_result = result
        self._started = True
        return result

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_error: Exception | None = None if self._reader_error_reported else self._reader_error
        if self._reader_task is not None:
            if not self._reader_task.done():
                self._reader_task.cancel()
            reader_result = await asyncio.gather(self._reader_task, return_exceptions=True)
            reader_error = reader_result[0]
            if isinstance(reader_error, Exception):
                close_error = reader_error
        self._fail_pending(AppServerClosedError("app-server client closed"))
        try:
            await self._transport.close()
        except Exception as exc:
            if close_error is None:
                close_error = exc
        finally:
            self._started = False
            self._initialize_result = None
            self._reader_task = None
            for sink in list(self._notification_sinks):
                await sink.queue.put(None)
            self._notification_sinks.clear()
        if close_error is not None:
            raise close_error

    async def _close_for_start_failure(self) -> Exception | None:
        try:
            await self.close()
        except Exception as exc:
            return exc
        return None

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
        return await self._await_future(future)

    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, Any] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        return parse_result(await self.request(method, params), result_model, method=method)

    def on_request(
        self,
        method: str,
        handler: RequestHandler[_RequestT],
        *,
        request_model: type[_RequestT] | None = None,
    ) -> None:
        self._request_handlers[method] = _RegisteredHandler(
            cast(RequestHandler[BaseModel], handler),
            request_model=cast(type[BaseModel] | None, request_model),
        )

    def subscribe_notifications(
        self,
        methods: Collection[str] | None = None,
        *,
        predicate: _NotificationPredicate | None = None,
    ) -> _AsyncNotificationSubscription:
        sink = _NotificationSink(None if methods is None else set(methods), predicate=predicate)
        self._notification_sinks.append(sink)
        return _AsyncNotificationSubscription(sink, sink.queue, lambda: self._remove_sink(sink))

    async def _ensure_started_or_starting(self) -> None:
        if self._closed:
            raise AppServerClosedError("app-server client is closed")
        if self._reader_task is None:
            raise AppServerClosedError("app-server client is not started")
        if self._reader_task.done():
            raise self._reader_failure()

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
            self._reader_error = exc
            self._fail_pending(exc)
            for sink in list(self._notification_sinks):
                await sink.queue.put(None)

    async def _await_future(self, future: asyncio.Future[object]) -> object:
        while True:
            if future.done():
                return self._future_result(future)
            if self._reader_task is not None and self._reader_task.done():
                raise self._reader_failure()
            done, _ = await asyncio.wait(
                {
                    cast(asyncio.Future[Any], future),
                    cast(asyncio.Future[Any], self._reader_task),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            if future in done:
                return self._future_result(future)
            if self._reader_task in done:
                raise self._reader_failure()

    def _future_result(self, future: asyncio.Future[object]) -> object:
        try:
            return future.result()
        except Exception as exc:
            if exc is self._reader_error:
                self._reader_error_reported = True
            raise

    def _reader_failure(self) -> Exception:
        if self._reader_error is not None:
            self._reader_error_reported = True
            return self._reader_error
        if self._reader_task is None:
            return AppServerClosedError("app-server client is not started")
        task_exception = self._reader_task.exception()
        if task_exception is not None:
            if isinstance(task_exception, Exception):
                self._reader_error_reported = True
                return task_exception
            return AppServerClosedError(f"app-server reader failed: {task_exception}")
        return AppServerClosedError("app-server reader stopped unexpectedly")

    def _handle_response(self, message: JsonObject) -> None:
        pending_id = message.get("id")
        future = self._pending.pop(cast(int | str, pending_id), None)
        if future is None:
            return
        if "error" in message:
            try:
                parsed = protocol.JSONRPCError.model_validate(message)
            except ValidationError as exc:
                error = AppServerProtocolError(
                    f"Malformed app-server error response envelope for request {pending_id!r}"
                )
                error.__cause__ = exc
                future.set_exception(error)
                return
            future.set_exception(
                AppServerRpcError(
                    parsed.error.code,
                    parsed.error.message,
                    parsed.error.data,
                )
            )
            return
        try:
            response = protocol.JSONRPCResponse.model_validate(message)
        except ValidationError as exc:
            error = AppServerProtocolError(
                f"Malformed app-server response envelope for request {pending_id!r}"
            )
            error.__cause__ = exc
            future.set_exception(error)
            return
        future.set_result(response.result)

    async def _broadcast_notification(self, message: JsonObject) -> None:
        notification = parse_notification(message, strict=self._strict_protocol)
        notification_method = method_name(notification)
        for sink in list(self._notification_sinks):
            if sink.matches(notification_method, notification):
                await sink.queue.put(notification)

    async def _handle_server_request(self, message: JsonObject) -> None:
        request = parse_server_request(message, strict=self._strict_protocol)
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
                request_value = _adapt_server_request_model(
                    request,
                    registered.request_model,
                    method=request_method,
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
                    "error": _jsonrpc_error_from_exception(exc),
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


def _jsonrpc_error_from_exception(exc: Exception) -> JsonObject:
    if isinstance(exc, AppServerRpcError):
        return {"code": exc.code, "message": exc.message, "data": exc.data}
    message = str(exc)
    summary = type(exc).__name__ if not message else f"{type(exc).__name__}: {message}"
    return {
        "code": -32000,
        "message": summary,
        "data": {
            "exceptionType": type(exc).__name__,
            "exceptionModule": type(exc).__module__,
            "exceptionMessage": message,
        },
    }


def _adapt_server_request_model[RequestModelT: BaseModel](
    request: BaseModel,
    request_model: type[RequestModelT],
    *,
    method: str,
) -> RequestModelT:
    if isinstance(request, request_model):
        return request
    try:
        return request_model.model_validate(serialize_value(request))
    except ValidationError as exc:
        raise AppServerProtocolError(
            f"Failed to parse app-server request {method!r} as {request_model.__name__}"
        ) from exc
