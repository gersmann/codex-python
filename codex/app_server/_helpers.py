from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, cast, get_args

from pydantic import BaseModel, ValidationError

from codex.app_server.errors import AppServerProtocolError
from codex.app_server.models import GenericNotification, GenericServerRequest
from codex.app_server.transports import JsonObject
from codex.protocol import types as protocol

InputItem = (
    str
    | Mapping[str, Any]
    | protocol.UserInput
    | protocol.TextUserInput
    | protocol.ImageUserInput
    | protocol.LocalImageUserInput
    | protocol.SkillUserInput
    | protocol.MentionUserInput
)
TurnInput = InputItem | Sequence[InputItem]
RequestHandler = Callable[[BaseModel], object | Awaitable[object]]
Notification = BaseModel


def _build_known_methods(*, root_model: type[BaseModel]) -> set[str]:
    methods: set[str] = set()
    root_field = getattr(root_model, "model_fields", {}).get("root")
    if root_field is None:
        return methods
    for candidate in get_args(root_field.annotation):
        if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
            continue
        model_fields = getattr(candidate, "model_fields", None)
        if not isinstance(model_fields, dict) or "method" not in model_fields:
            continue
        annotation = getattr(model_fields["method"], "annotation", None)
        if not isinstance(annotation, type) or not issubclass(annotation, BaseModel):
            continue
        root_fields = getattr(annotation, "model_fields", None)
        if not isinstance(root_fields, dict) or "root" not in root_fields:
            continue
        root_annotation = getattr(root_fields["root"], "annotation", None)
        literal_args = get_args(root_annotation)
        if len(literal_args) == 1 and isinstance(literal_args[0], str):
            methods.add(literal_args[0])
    return methods


KNOWN_NOTIFICATION_METHODS = _build_known_methods(root_model=protocol.ServerNotification)
KNOWN_SERVER_REQUEST_METHODS = _build_known_methods(root_model=protocol.ServerRequest)


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


def serialize_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, type) and issubclass(value, BaseModel):
        return value.model_json_schema()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {key: serialize_value(item) for key, item in value.items()}
    return value


def normalize_input_item(item: InputItem) -> JsonObject:
    if isinstance(item, str):
        return {"type": "text", "text": item}
    serialized = serialize_value(item)
    if not isinstance(serialized, dict):
        raise TypeError(f"Input item must serialize to an object, got {type(serialized).__name__}")
    return cast(JsonObject, serialized)


def normalize_turn_input(value: TurnInput) -> list[JsonObject]:
    if isinstance(value, str):
        return [{"type": "text", "text": value}]
    if isinstance(value, Sequence):
        return [normalize_input_item(item) for item in value]
    return [normalize_input_item(value)]


def merge_params(
    params: BaseModel | Mapping[str, Any] | None = None,
    **overrides: object,
) -> JsonObject:
    payload: JsonObject = {}
    if params is not None:
        serialized = serialize_value(params)
        if not isinstance(serialized, dict):
            raise TypeError(
                f"RPC params must serialize to an object, got {type(serialized).__name__}"
            )
        payload.update(cast(JsonObject, serialized))
    for key, value in overrides.items():
        if value is not None:
            payload[key] = serialize_value(value)
    return payload


def has_output_schema(params: BaseModel | Mapping[str, Any] | None) -> bool:
    if params is None:
        return False
    if isinstance(params, BaseModel):
        return getattr(params, "outputSchema", None) is not None
    return params.get("outputSchema") is not None or params.get("output_schema") is not None


def parse_result(result: object, result_model: type[BaseModel]) -> BaseModel:
    if isinstance(result, result_model):
        return result
    payload = {} if result is None else result
    return result_model.model_validate(payload)


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
        if strict or not isinstance(method, str) or method in KNOWN_NOTIFICATION_METHODS:
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
        if strict or not isinstance(method, str) or method in KNOWN_SERVER_REQUEST_METHODS:
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
