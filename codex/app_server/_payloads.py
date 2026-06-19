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


def skill_input(*, name: str, path: str) -> protocol.SkillUserInput:
    if name == "":
        raise ValueError("Skill name cannot be empty.")
    if name.startswith("$"):
        raise ValueError("Skill name should not include the '$' activation marker.")
    if any(character.isspace() for character in name):
        raise ValueError("Skill name cannot contain whitespace.")
    if "/" in name or "\\" in name:
        raise ValueError("Skill name cannot contain path separators.")
    if path == "":
        raise ValueError("Skill path cannot be empty.")
    return protocol.SkillUserInput(
        type=protocol.SkillUserInputType("skill"),
        name=name,
        path=path,
    )


def _add_skill_markers(
    items: list[JsonObject],
    skills: Sequence[protocol.SkillUserInput],
) -> list[JsonObject]:
    if not skills:
        return items
    markers = " ".join(f"${skill.name}" for skill in skills)
    for item in items:
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            item["text"] = f"{markers}\n\n{text}"
            return items
    return [{"type": "text", "text": markers}, *items]


def normalize_turn_input(
    value: TurnInput,
    *,
    skills: Sequence[protocol.SkillUserInput] | None = None,
) -> list[JsonObject]:
    if isinstance(value, str):
        items = [{"type": "text", "text": value}]
    elif isinstance(value, Sequence):
        items = [normalize_input_item(item) for item in value]
    else:
        items = [normalize_input_item(value)]
    if skills is None:
        return items
    return _add_skill_markers(items, skills) + [normalize_input_item(skill) for skill in skills]
