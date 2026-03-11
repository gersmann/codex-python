from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import BaseModel

from codex.app_server._types import JsonObject
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

type ParamsModel = BaseModel


def serialize_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_unset=True,
        )
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
