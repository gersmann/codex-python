from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast, get_type_hints, overload

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from codex.protocol import types as protocol

_DYNAMIC_TOOL_ATTR = "__codex_dynamic_tool__"


@dataclass(frozen=True, slots=True)
class _DynamicToolMetadata:
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedDynamicTool:
    callable: Callable[..., object]
    description: str
    input_model: type[BaseModel]
    name: str

    def spec(self) -> protocol.DynamicToolSpec:
        return protocol.DynamicToolSpec(
            name=self.name,
            description=self.description,
            inputSchema=self.input_model.model_json_schema(),
        )


class _HandlerInstaller(Protocol):
    def __call__(
        self,
        method: str,
        handler: Callable[[protocol.ItemToolCallRequest], object | Awaitable[object]],
        *,
        request_model: type[protocol.ItemToolCallRequest],
    ) -> None: ...


@overload
def dynamic_tool(func: Callable[..., object], /) -> Callable[..., object]: ...


@overload
def dynamic_tool(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[..., object]], Callable[..., object]]: ...


def dynamic_tool(
    func: Callable[..., object] | None = None,
    /,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[..., object] | Callable[[Callable[..., object]], Callable[..., object]]:
    """Mark a callable as a dynamic tool definition."""

    def decorate(callable_obj: Callable[..., object]) -> Callable[..., object]:
        owner = _callable_owner(callable_obj)
        setattr(owner, _DYNAMIC_TOOL_ATTR, _DynamicToolMetadata(name=name, description=description))
        return callable_obj

    if func is not None:
        return decorate(func)
    return decorate


def resolve_dynamic_tools(tools: Sequence[Callable[..., object]]) -> list[_ResolvedDynamicTool]:
    resolved = [_resolve_dynamic_tool(tool) for tool in tools]
    _raise_on_duplicate_names(tool.name for tool in resolved)
    return resolved


def merge_dynamic_tool_specs(
    raw_specs: Sequence[protocol.DynamicToolSpec] | None,
    resolved_tools: Sequence[_ResolvedDynamicTool],
) -> list[protocol.DynamicToolSpec] | None:
    merged = list(raw_specs or [])
    _raise_on_duplicate_names(spec.name for spec in merged)
    _raise_on_duplicate_names(
        [spec.name for spec in merged] + [tool.name for tool in resolved_tools]
    )
    if not merged and not resolved_tools:
        return None
    merged.extend(tool.spec() for tool in resolved_tools)
    return merged


class _DynamicToolRuntime:
    def __init__(self, install_handler: _HandlerInstaller) -> None:
        self._install_handler = install_handler
        self._mode: str | None = None
        self._tools: dict[tuple[str, str], _ResolvedDynamicTool] = {}

    def check_manual_handler_registration(self, method: str) -> None:
        if method != "item/tool/call":
            return
        if self._mode == "dispatcher":
            raise ValueError(
                "item/tool/call is reserved for annotation-driven dynamic tools on this client"
            )
        self._mode = "manual"

    def activate(
        self,
        thread_id: str,
        resolved_tools: Sequence[_ResolvedDynamicTool],
    ) -> None:
        if not resolved_tools:
            return
        _raise_on_duplicate_names(tool.name for tool in resolved_tools)
        for tool in resolved_tools:
            self._tools[(thread_id, tool.name)] = tool

    def prepare_activation(self, resolved_tools: Sequence[_ResolvedDynamicTool]) -> None:
        if not resolved_tools:
            return
        _raise_on_duplicate_names(tool.name for tool in resolved_tools)
        self._ensure_dispatcher_installed()

    async def dispatch(
        self, request: protocol.ItemToolCallRequest
    ) -> protocol.DynamicToolCallResponse:
        tool = self._tools.get((request.params.threadId, request.params.tool))
        if tool is None:
            raise ValueError(
                f"No annotation-driven dynamic tool named {request.params.tool!r} is active for thread "
                f"{request.params.threadId!r}"
            )

        validated = tool.input_model.model_validate(request.params.arguments)
        arguments = validated.model_dump(mode="python")
        result = tool.callable(**arguments)
        if inspect.isawaitable(result):
            result = await cast(Awaitable[object], result)
        return _normalize_tool_result(result)

    def _ensure_dispatcher_installed(self) -> None:
        if self._mode == "manual":
            raise ValueError(
                "Cannot activate annotation-driven dynamic tools after registering a manual "
                "item/tool/call handler"
            )
        if self._mode == "dispatcher":
            return
        self._install_handler(
            "item/tool/call",
            self.dispatch,
            request_model=protocol.ItemToolCallRequest,
        )
        self._mode = "dispatcher"


def _resolve_dynamic_tool(tool: Callable[..., object]) -> _ResolvedDynamicTool:
    metadata = getattr(_callable_owner(tool), _DYNAMIC_TOOL_ATTR, None)
    if not isinstance(metadata, _DynamicToolMetadata):
        raise ValueError(
            f"{_callable_name(tool)!r} is not marked as a dynamic tool; use @dynamic_tool first"
        )

    name = metadata.name or _callable_name(tool)
    description = metadata.description or _docstring_summary(tool)
    if description is None:
        raise ValueError(f"Dynamic tool {name!r} must define a description or docstring")

    return _ResolvedDynamicTool(
        callable=tool,
        name=name,
        description=description,
        input_model=_build_input_model(tool, tool_name=name),
    )


def _build_input_model(tool: Callable[..., object], *, tool_name: str) -> type[BaseModel]:
    signature = inspect.signature(tool)
    type_hints = get_type_hints(tool, include_extras=True)
    fields: dict[str, tuple[object, object]] = {}

    for parameter in signature.parameters.values():
        if parameter.name in {"self", "cls"}:
            raise ValueError(
                f"Dynamic tool {tool_name!r} must be a bound method or standalone function"
            )
        if parameter.kind not in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }:
            raise ValueError(
                f"Dynamic tool {tool_name!r} parameter {parameter.name!r} must be a named argument"
            )
        annotation = type_hints.get(parameter.name, parameter.annotation)
        if annotation is inspect.Signature.empty:
            raise ValueError(
                f"Dynamic tool {tool_name!r} parameter {parameter.name!r} must have a type annotation"
            )
        default = ... if parameter.default is inspect.Signature.empty else parameter.default
        fields[parameter.name] = (annotation, default)

    model_name = f"{_pascal_case(tool_name)}DynamicToolInput"
    model = create_model(
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **cast(dict[str, Any], fields),
    )
    return cast(type[BaseModel], model)


def _normalize_tool_result(result: object) -> protocol.DynamicToolCallResponse:
    try:
        return protocol.DynamicToolCallResponse.model_validate(result)
    except ValidationError:
        pass

    content_items = _maybe_content_items(result)
    if content_items is not None:
        return protocol.DynamicToolCallResponse(contentItems=content_items, success=True)

    if isinstance(result, str):
        return protocol.DynamicToolCallResponse(
            contentItems=[_text_content_item(result)],
            success=True,
        )

    return protocol.DynamicToolCallResponse(
        contentItems=[_text_content_item(json.dumps(_serialize_value(result)))],
        success=True,
    )


def _maybe_content_items(
    value: object,
) -> list[protocol.DynamicToolCallOutputContentItem] | None:
    if isinstance(value, str):
        return None

    try:
        item = protocol.DynamicToolCallOutputContentItem.model_validate(value)
    except ValidationError:
        item = None
    if item is not None:
        return [item]

    if not isinstance(value, Sequence):
        return None

    items: list[protocol.DynamicToolCallOutputContentItem] = []
    for item_value in value:
        try:
            items.append(protocol.DynamicToolCallOutputContentItem.model_validate(item_value))
        except ValidationError:
            return None
    return items


def _text_content_item(text: str) -> protocol.DynamicToolCallOutputContentItem:
    return protocol.DynamicToolCallOutputContentItem.model_validate(
        {"type": "inputText", "text": text}
    )


def _serialize_value(value: object) -> object:
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
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _callable_owner(tool: Callable[..., object]) -> object:
    return getattr(tool, "__func__", tool)


def _callable_name(tool: Callable[..., object]) -> str:
    owner = _callable_owner(tool)
    name = getattr(owner, "__name__", None)
    if isinstance(name, str) and name != "":
        return name
    raise ValueError(f"Dynamic tool callable is missing a usable __name__: {tool!r}")


def _docstring_summary(tool: Callable[..., object]) -> str | None:
    docstring = inspect.getdoc(tool)
    if docstring is None:
        return None
    for line in docstring.splitlines():
        summary = line.strip()
        if summary:
            return summary
    return None


def _pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _raise_on_duplicate_names(names: Iterable[str]) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"Duplicate dynamic tool name {name!r}")
        seen.add(name)


__all__ = ["dynamic_tool"]
