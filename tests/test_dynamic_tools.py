from __future__ import annotations

import asyncio
import json
from typing import Annotated

import pytest
from pydantic import Field

from codex.dynamic_tools import (
    _DynamicToolRuntime,
    dynamic_tool,
    resolve_dynamic_tools,
)
from codex.protocol import types as protocol


def test_dynamic_tool_derives_schema_from_typed_parameters() -> None:
    @dynamic_tool
    def lookup_ticket(
        ticket_id: Annotated[str, Field(description="Ticket identifier")],
        include_logs: bool = False,
    ) -> str:
        """Look up a support ticket."""
        return f"Ticket {ticket_id}"

    resolved = resolve_dynamic_tools([lookup_ticket])[0]
    spec = resolved.spec()

    assert spec.name == "lookup_ticket"
    assert spec.description == "Look up a support ticket."
    assert spec.inputSchema["type"] == "object"
    assert spec.inputSchema["additionalProperties"] is False
    assert spec.inputSchema["required"] == ["ticket_id"]
    assert spec.inputSchema["properties"]["ticket_id"] == {
        "description": "Ticket identifier",
        "title": "Ticket Id",
        "type": "string",
    }
    assert spec.inputSchema["properties"]["include_logs"] == {
        "default": False,
        "title": "Include Logs",
        "type": "boolean",
    }


def test_dynamic_tool_runtime_dispatches_bound_methods_and_json_serializable_results() -> None:
    class SupportDesk:
        def __init__(self) -> None:
            self.calls: list[tuple[str, bool]] = []

        @dynamic_tool(description="Look up a support ticket by id.")
        def lookup_ticket(self, id: str, include_logs: bool = False) -> dict[str, object]:
            self.calls.append((id, include_logs))
            return {"id": id, "include_logs": include_logs}

    support_desk = SupportDesk()
    runtime = _DynamicToolRuntime(lambda method, handler, request_model: None)
    runtime.activate("thr-1", resolve_dynamic_tools([support_desk.lookup_ticket]))

    request = protocol.ItemToolCallRequest.model_validate(
        {
            "id": "req-1",
            "method": "item/tool/call",
            "params": {
                "callId": "call-1",
                "threadId": "thr-1",
                "turnId": "turn-1",
                "tool": "lookup_ticket",
                "arguments": {"id": "123", "include_logs": True},
            },
        }
    )

    response = asyncio.run(runtime.dispatch(request))

    assert support_desk.calls == [("123", True)]
    assert response.success is True
    assert json.loads(response.contentItems[0].root.text) == {"id": "123", "include_logs": True}


def test_dynamic_tool_runtime_supports_async_tools_and_structured_content_items() -> None:
    @dynamic_tool(description="Render an image preview.")
    async def preview_image(url: str) -> list[dict[str, str]]:
        return [{"type": "inputImage", "imageUrl": url}]

    runtime = _DynamicToolRuntime(lambda method, handler, request_model: None)
    runtime.activate("thr-2", resolve_dynamic_tools([preview_image]))

    request = protocol.ItemToolCallRequest.model_validate(
        {
            "id": "req-2",
            "method": "item/tool/call",
            "params": {
                "callId": "call-2",
                "threadId": "thr-2",
                "turnId": "turn-2",
                "tool": "preview_image",
                "arguments": {"url": "https://example.test/image.png"},
            },
        }
    )

    response = asyncio.run(runtime.dispatch(request))

    assert response.success is True
    assert response.contentItems[0].root.imageUrl == "https://example.test/image.png"


def test_dynamic_tool_rejects_invalid_signatures() -> None:
    @dynamic_tool(description="Missing annotation.")
    def missing_annotation(ticket_id) -> str:  # type: ignore[no-untyped-def]
        return str(ticket_id)

    @dynamic_tool(description="Varargs are not supported.")
    def has_varargs(*ticket_ids: str) -> str:
        return ",".join(ticket_ids)

    class SupportDesk:
        @dynamic_tool(description="Unbound instance method.")
        def lookup_ticket(self, id: str) -> str:
            return id

    with pytest.raises(ValueError, match="must have a type annotation"):
        resolve_dynamic_tools([missing_annotation])
    with pytest.raises(ValueError, match="must be a named argument"):
        resolve_dynamic_tools([has_varargs])
    with pytest.raises(ValueError, match="bound method or standalone function"):
        resolve_dynamic_tools([SupportDesk.lookup_ticket])


def test_dynamic_tool_runtime_rejects_conflicting_handlers_and_duplicate_names() -> None:
    registrations: list[tuple[str, object, object]] = []

    @dynamic_tool(description="Look up a support ticket by id.")
    def lookup_ticket(id: str) -> str:
        return id

    @dynamic_tool(name="lookup_ticket", description="Duplicate name.")
    def lookup_other_ticket(id: str) -> str:
        return id

    runtime = _DynamicToolRuntime(
        lambda method, handler, request_model: registrations.append(
            (method, handler, request_model)
        )
    )
    resolved = resolve_dynamic_tools([lookup_ticket])
    runtime.prepare_activation(resolved)
    runtime.activate("thr-1", resolved)

    assert registrations[0][0] == "item/tool/call"
    assert registrations[0][2] is protocol.ItemToolCallRequest

    with pytest.raises(
        ValueError,
        match="item/tool/call is reserved for annotation-driven dynamic tools",
    ):
        runtime.check_manual_handler_registration("item/tool/call")

    with pytest.raises(ValueError, match="Duplicate dynamic tool name 'lookup_ticket'"):
        resolve_dynamic_tools([lookup_ticket, lookup_other_ticket])

    manual_runtime = _DynamicToolRuntime(lambda method, handler, request_model: None)
    manual_runtime.check_manual_handler_registration("item/tool/call")
    with pytest.raises(
        ValueError,
        match="Cannot activate annotation-driven dynamic tools after registering a manual",
    ):
        manual_runtime.prepare_activation(resolve_dynamic_tools([lookup_ticket]))
