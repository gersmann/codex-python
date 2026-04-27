from __future__ import annotations

import pytest
from pydantic import BaseModel

from codex.app_server._payloads import normalize_input_item, normalize_turn_input, serialize_value
from codex.app_server._protocol_helpers import (
    extract_item,
    extract_text_delta,
    extract_thread_id,
    extract_token_usage,
    extract_turn,
    extract_turn_id,
    method_name,
    parse_notification,
    parse_result,
    parse_server_request,
    request_id,
)
from codex.app_server.errors import AppServerProtocolError
from codex.app_server.models import EmptyResult, GenericNotification, GenericServerRequest
from codex.protocol import types as protocol


class _SchemaModel(BaseModel):
    answer: str


def _turn_payload(turn_id: str = "turn-1") -> dict[str, object]:
    return {
        "id": turn_id,
        "status": "completed",
        "items": [],
        "error": None,
    }


def test_serialize_value_handles_models_model_classes_and_sequences() -> None:
    payload = _SchemaModel(answer="ok")

    assert serialize_value(payload) == {"answer": "ok"}
    assert serialize_value(_SchemaModel) == _SchemaModel.model_json_schema()
    assert serialize_value((payload, {"items": [payload]})) == [
        {"answer": "ok"},
        {"items": [{"answer": "ok"}]},
    ]


def test_normalize_turn_input_wraps_strings_and_objects() -> None:
    assert normalize_input_item("hello") == {"type": "text", "text": "hello"}
    assert normalize_turn_input("hello") == [{"type": "text", "text": "hello"}]
    assert normalize_turn_input(
        [
            {"type": "text", "text": "hello"},
            protocol.LocalImageUserInput(type="localImage", path="/tmp/example.png"),
        ]
    ) == [
        {"type": "text", "text": "hello"},
        {"type": "localImage", "path": "/tmp/example.png"},
    ]

    with pytest.raises(TypeError, match="serialize to an object"):
        normalize_input_item(123)  # type: ignore[arg-type]


def test_parse_result_reuses_existing_model_and_normalizes_none() -> None:
    existing = EmptyResult()

    assert parse_result(existing, EmptyResult) is existing
    assert parse_result(None, EmptyResult) == EmptyResult()


def test_parse_notification_allows_generic_unknown_methods_in_non_strict_mode() -> None:
    parsed = parse_notification(
        {"method": "custom/notify", "params": {"ok": True}},
        strict=False,
    )

    assert parsed == GenericNotification(method="custom/notify", params={"ok": True})
    assert method_name(parsed) == "custom/notify"


def test_parse_notification_rejects_unknown_methods_in_strict_mode() -> None:
    with pytest.raises(AppServerProtocolError, match="custom/notify"):
        parse_notification({"method": "custom/notify", "params": {"ok": True}}, strict=True)


def test_parse_server_request_allows_generic_unknown_methods_in_non_strict_mode() -> None:
    parsed = parse_server_request(
        {"id": "req-1", "method": "custom/request", "params": {"ok": True}},
        strict=False,
    )

    assert parsed == GenericServerRequest(id="req-1", method="custom/request", params={"ok": True})
    assert method_name(parsed) == "custom/request"
    assert request_id(parsed) == "req-1"


def test_parse_server_request_handles_permissions_approval_request() -> None:
    parsed = parse_server_request(
        {
            "id": "req-1",
            "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "itemId": "item-1",
                "permissions": {
                    "network": {"enabled": True},
                    "fileSystem": {"read": ["/repo"], "write": ["/tmp/out"]},
                },
                "reason": "Tool requested additional access.",
            },
        },
        strict=True,
    )

    assert isinstance(parsed, protocol.ItemPermissionsRequestApprovalRequest)
    assert method_name(parsed) == "item/permissions/requestApproval"
    assert request_id(parsed) == "req-1"
    assert parsed.params.permissions.network is not None
    assert parsed.params.permissions.network.enabled is True


def test_parse_server_request_rejects_invalid_shapes() -> None:
    with pytest.raises(AppServerProtocolError, match="custom/request"):
        parse_server_request(
            {"id": "req-1", "method": "custom/request", "params": ["bad"]},
            strict=False,
        )


def test_extract_helpers_read_turn_notification_fields() -> None:
    notification = protocol.TurnCompletedNotificationModel.model_validate(
        {
            "method": "turn/completed",
            "params": {
                "threadId": "thr-1",
                "turn": _turn_payload(),
            },
        }
    )

    assert extract_thread_id(notification) == "thr-1"
    assert extract_turn_id(notification) == "turn-1"
    assert extract_turn(notification) is not None
    assert extract_item(notification) is None


def test_extract_helpers_read_item_deltas_and_usage() -> None:
    delta = protocol.ItemAgentMessageDeltaNotification.model_validate(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "itemId": "item-1",
                "delta": "hello",
            },
        }
    )
    item_notification = protocol.ItemCompletedNotificationModel.model_validate(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "item": {
                    "id": "item-1",
                    "type": "agentMessage",
                    "text": "hello",
                    "phase": "final_answer",
                },
            },
        }
    )
    usage_notification = protocol.ThreadTokenUsageUpdatedNotificationModel.model_validate(
        {
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "tokenUsage": {
                    "last": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                    "total": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                },
            },
        }
    )

    assert extract_text_delta(delta) == "hello"
    assert extract_item(item_notification) is not None
    usage = extract_token_usage(usage_notification)
    assert usage is not None
    assert usage.total.totalTokens == 3
