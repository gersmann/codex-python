from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from functools import lru_cache
from typing import get_args

from pydantic import BaseModel, ValidationError

from codex.app_server._types import JsonObject
from codex.app_server.errors import AppServerProtocolError
from codex.app_server.models import GenericNotification, GenericServerRequest
from codex.protocol import types as protocol

type RequestHandler[RequestT: BaseModel] = Callable[[RequestT], object | Awaitable[object]]
Notification = BaseModel


def method_name(message: BaseModel) -> str:
    if isinstance(message, GenericNotification | GenericServerRequest):
        return message.method
    method = getattr(message, "method", None)
    if isinstance(method, BaseModel) and hasattr(method, "root"):
        root = method.root
        if isinstance(root, str):
            return root
    if isinstance(method, str):
        return method
    raise AppServerProtocolError(f"Message is missing a valid method: {message!r}")


def request_id(message: BaseModel) -> str | int:
    if isinstance(message, GenericServerRequest):
        return message.id
    message_id = getattr(message, "id", None)
    if isinstance(message_id, BaseModel) and hasattr(message_id, "root"):
        root = message_id.root
        if isinstance(root, str | int):
            return root
    if isinstance(message_id, str | int):
        return message_id
    raise AppServerProtocolError(f"Message is missing a valid request id: {message!r}")


def parse_result[ModelT: BaseModel](
    result: object,
    result_model: type[ModelT],
    *,
    method: str | None = None,
) -> ModelT:
    if isinstance(result, result_model):
        return result
    payload = {} if result is None else result
    try:
        return result_model.model_validate(payload)
    except ValidationError as exc:
        method_context = f" for app-server method {method!r}" if method is not None else ""
        raise AppServerProtocolError(
            f"Failed to parse app-server result{method_context} as {result_model.__name__}"
        ) from exc


def extract_thread_id(notification: BaseModel) -> str | None:
    params = getattr(notification, "params", None)
    if params is None:
        return None
    thread_id = getattr(params, "threadId", None)
    return thread_id if isinstance(thread_id, str) else None


def extract_turn_id(notification: BaseModel) -> str | None:
    params = getattr(notification, "params", None)
    if params is None:
        return None
    turn_id = getattr(params, "turnId", None)
    if isinstance(turn_id, str):
        return turn_id
    turn = getattr(params, "turn", None)
    if isinstance(turn, protocol.Turn):
        return turn.id
    return None


def extract_item(notification: BaseModel) -> protocol.ThreadItem | None:
    params = getattr(notification, "params", None)
    item = getattr(params, "item", None) if params is not None else None
    return item if isinstance(item, protocol.ThreadItem) else None


def extract_turn(notification: BaseModel) -> protocol.Turn | None:
    params = getattr(notification, "params", None)
    turn = getattr(params, "turn", None) if params is not None else None
    return turn if isinstance(turn, protocol.Turn) else None


def extract_text_delta(notification: BaseModel) -> str | None:
    if isinstance(notification, protocol.ItemAgentMessageDeltaNotification):
        return notification.params.delta
    return None


def extract_token_usage(notification: BaseModel) -> protocol.ThreadTokenUsage | None:
    if isinstance(notification, protocol.ThreadTokenUsageUpdatedNotificationModel):
        return notification.params.tokenUsage
    return None


def parse_notification(message: JsonObject, *, strict: bool) -> Notification:
    method = message.get("method")
    try:
        return protocol.ServerNotification.model_validate(message).root
    except ValidationError as exc:
        if (
            strict
            or not isinstance(method, str)
            or method in _known_methods(protocol.ServerNotification)
        ):
            raise AppServerProtocolError(_notification_error_message(message)) from exc
        params = message.get("params")
        if params is None:
            return GenericNotification(method=method)
        if isinstance(params, Mapping):
            return GenericNotification(method=method, params=dict(params))
        raise AppServerProtocolError(_notification_error_message(message)) from exc


def parse_server_request(message: JsonObject, *, strict: bool) -> BaseModel:
    method = message.get("method")
    try:
        return protocol.ServerRequest.model_validate(message).root
    except ValidationError as exc:
        if (
            strict
            or not isinstance(method, str)
            or method in _known_methods(protocol.ServerRequest)
        ):
            raise AppServerProtocolError(_server_request_error_message(message)) from exc
        params = message.get("params")
        if params is None:
            params_payload: dict[str, object] = {}
        elif isinstance(params, Mapping):
            params_payload = dict(params)
        else:
            raise AppServerProtocolError(_server_request_error_message(message)) from exc
        raw_id = message.get("id")
        if not isinstance(raw_id, str | int):
            raise AppServerProtocolError(_server_request_error_message(message)) from exc
        return GenericServerRequest(id=raw_id, method=method, params=params_payload)


def _build_known_methods(*, root_model: type[BaseModel]) -> frozenset[str]:
    root_field = getattr(root_model, "model_fields", {}).get("root")
    if root_field is None:
        return frozenset()
    methods = {
        method
        for candidate in get_args(root_field.annotation)
        if isinstance(candidate, type) and issubclass(candidate, BaseModel)
        for method in [_candidate_method_literal(candidate)]
        if method is not None
    }
    return frozenset(methods)


def _candidate_method_literal(candidate: type[BaseModel]) -> str | None:
    model_fields = getattr(candidate, "model_fields", None)
    if not isinstance(model_fields, dict) or "method" not in model_fields:
        return None
    annotation = getattr(model_fields["method"], "annotation", None)
    if not isinstance(annotation, type) or not issubclass(annotation, BaseModel):
        return None
    return _root_literal(annotation)


def _root_literal(model: type[BaseModel]) -> str | None:
    root_fields = getattr(model, "model_fields", None)
    if not isinstance(root_fields, dict) or "root" not in root_fields:
        return None
    root_annotation = getattr(root_fields["root"], "annotation", None)
    literal_args = get_args(root_annotation)
    if len(literal_args) == 1 and isinstance(literal_args[0], str):
        return literal_args[0]
    return None


@lru_cache(maxsize=2)
def _known_methods(root_model: type[BaseModel]) -> frozenset[str]:
    return _build_known_methods(root_model=root_model)


def _notification_error_message(message: JsonObject) -> str:
    method = message.get("method")
    if isinstance(method, str):
        return f"Unsupported app-server notification method {method!r}"
    return f"Unsupported app-server notification: {message!r}"


def _server_request_error_message(message: JsonObject) -> str:
    method = message.get("method")
    if isinstance(method, str):
        return f"Unsupported app-server server request method {method!r}"
    return f"Unsupported app-server server request: {message!r}"
