"""Keep hand-written app-server models as permissive as the generated protocol."""

from __future__ import annotations

import inspect
import re
import types
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal, TypeAliasType, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, RootModel

from codex.app_server import models
from codex.protocol import types as protocol

type WireKind = tuple[str, object]

ANY: WireKind = ("kind", "any")

# Every generated field must exist on these; the rest are checked where fields overlap.
FULL_MIRRORS: dict[type[BaseModel], type[BaseModel]] = {
    models.AccountRateLimitsResult: protocol.GetAccountRateLimitsResponse,
    models.AccountReadResult: protocol.GetAccountResponse,
    models.ApiKeyAccountInfo: protocol.ApiKeyAccount,
    models.ChatGptAccountInfo: protocol.ChatgptAccount,
    models.ConfigRequirements: protocol.ConfigRequirements,
    models.ConfigRequirementsReadResult: protocol.ConfigRequirementsReadResponse,
    models.InitializeResult: protocol.InitializeResponse,
    models.McpServerOauthLoginResult: protocol.McpServerOauthLoginResponse,
    models.McpServerStatus: protocol.McpServerStatus,
    models.ModelInfo: protocol.Model,
    models.ModelUpgradeInfo: protocol.ModelUpgradeInfo,
    models.SkillInfo: protocol.SkillMetadata,
    models.SkillInterface: protocol.SkillInterface,
}
PARTIAL_MIRRORS: dict[type[BaseModel], type[BaseModel]] = {
    models.AppServerConfig: protocol.Config,
    models.ReviewResult: protocol.ReviewStartResponse,
    models.ThreadResult: protocol.ThreadStartResponse,
}


def _wire_kinds(annotation: object) -> set[WireKind]:
    origin = get_origin(annotation)
    if annotation is None or annotation is types.NoneType:
        return {("kind", "null")}
    if annotation is Any:
        return {ANY}
    if isinstance(annotation, TypeAliasType):
        return _wire_kinds(annotation.__value__)
    if origin is Annotated:
        return _wire_kinds(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        return {kind for arg in get_args(annotation) for kind in _wire_kinds(arg)}
    if origin is Literal:
        return {("literal", value) for value in get_args(annotation)}
    if origin is list or origin is Sequence or annotation is list:
        return {("kind", "list")}
    if origin is dict or origin is Mapping or annotation is dict:
        return {("kind", "object")}
    if inspect.isclass(annotation):
        if issubclass(annotation, RootModel):
            return _wire_kinds(annotation.model_fields["root"].annotation)
        if issubclass(annotation, BaseModel):
            return {("kind", "object")}
        if annotation in (str, int, float, bool):
            return {("kind", annotation.__name__)}
    return {ANY}


def _covered(kind: WireKind, accepted: set[WireKind]) -> bool:
    if kind in accepted or ANY in accepted or kind == ANY:
        return True
    value = kind[1]
    if kind[0] == "literal":
        return ("kind", type(value).__name__) in accepted
    return kind == ("kind", "int") and ("kind", "float") in accepted


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _generated_field(generated: type[BaseModel], name: str) -> Any:
    fields = generated.model_fields
    return fields.get(_camel(name)) or fields.get(name)


@pytest.mark.parametrize(
    ("handwritten", "generated"),
    [*FULL_MIRRORS.items(), *PARTIAL_MIRRORS.items()],
    ids=lambda model: model.__name__,
)
def test_handwritten_fields_accept_everything_the_protocol_allows(
    handwritten: type[BaseModel], generated: type[BaseModel]
) -> None:
    problems: list[str] = []
    for name, field in handwritten.model_fields.items():
        generated_field = _generated_field(generated, name)
        if generated_field is None:
            continue
        accepted = _wire_kinds(field.annotation)
        missing = {
            kind for kind in _wire_kinds(generated_field.annotation) if not _covered(kind, accepted)
        }
        if missing:
            problems.append(f"{name} rejects {sorted(map(str, missing))}")
        if field.is_required() and not generated_field.is_required():
            problems.append(f"{name} is required but the protocol allows omitting it")

    assert problems == []


@pytest.mark.parametrize(
    ("handwritten", "generated"),
    list(FULL_MIRRORS.items()),
    ids=lambda model: model.__name__,
)
def test_handwritten_models_keep_every_protocol_field(
    handwritten: type[BaseModel], generated: type[BaseModel]
) -> None:
    fields = set(handwritten.model_fields)

    assert sorted({_snake(name) for name in generated.model_fields} - fields) == []
