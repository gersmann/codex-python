from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, RootModel, field_serializer

from codex._config_types import CodexConfig
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
from codex.app_server.models import (
    AccountReadResult,
    ChatGptAccountInfo,
    ConfigReadResult,
    EmptyResult,
    GenericNotification,
    GenericServerRequest,
    ModelInfo,
)
from codex.app_server.options import (
    AppServerClientInfo,
    AppServerInitializeOptions,
    AppServerThreadForkOptions,
    AppServerThreadListOptions,
    AppServerTurnOptions,
)
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
    assert serialize_value(
        protocol.ThreadSectionMoveParams(
            sectionId=None,
            threadId="thread-1",
        )
    ) == {"sectionId": None, "threadId": "thread-1"}
    assert serialize_value(
        protocol.TurnSettingsUpdateParams(
            serviceTier=None,
            threadId="thread-1",
            turnId="turn-1",
        )
    ) == {"serviceTier": None, "threadId": "thread-1", "turnId": "turn-1"}
    assert serialize_value(
        protocol.TurnSettingsUpdateParams(threadId="thread-1", turnId="turn-1")
    ) == {"threadId": "thread-1", "turnId": "turn-1"}
    assert serialize_value(
        protocol.ThreadSettingsUpdateParams(serviceTier=None, threadId="thread-1")
    ) == {"serviceTier": None, "threadId": "thread-1"}
    assert serialize_value(protocol.ThreadSettingsUpdateParams(threadId="thread-1")) == {
        "threadId": "thread-1"
    }
    assert serialize_value(CodexConfig(custom_setting=True)) == {"custom_setting": True}


def test_serialize_value_preserves_nested_required_nulls() -> None:
    params = protocol.McpResourceReadParams(
        server="apps",
        uri="ui://resource",
        threadId=None,
        target=protocol.McpResourceReadTarget(connectorId="connector-1", linkId=None),
    )
    expected = {
        "server": "apps",
        "uri": "ui://resource",
        "threadId": None,
        "target": {"connectorId": "connector-1", "linkId": None},
    }

    assert serialize_value(params) == expected
    assert serialize_value(RootModel[list[protocol.McpResourceReadParams]]([params])) == [expected]
    assert serialize_value(
        RootModel[dict[str, protocol.McpResourceReadParams | None]](
            {"request": params, "other": None}
        )
    ) == {"request": expected, "other": None}


def test_serialize_value_preserves_pydantic_serializers_and_exclusions() -> None:
    class Payload(BaseModel):
        required_null: str | None = Field(serialization_alias="requiredNull")
        omitted: str | None = None
        hidden: str | None = Field(exclude=True)
        number: int

        @field_serializer("number")
        def serialize_number(self, value: int) -> str:
            return f"number-{value}"

    payload = Payload(required_null=None, omitted=None, hidden=None, number=3)
    assert serialize_value(RootModel[Payload](payload)) == {
        "requiredNull": None,
        "number": "number-3",
    }
    assert serialize_value(CodexConfig(custom_setting=None)) == {}


@pytest.mark.parametrize("reference", [{"url": "https://example.com/image.png"}, {"fileId": "f-1"}])
def test_normalize_turn_input_accepts_image_root_models(reference: dict[str, str]) -> None:
    payload = {"type": "image", "detail": None, **reference}
    image = protocol.ImageUserInput.model_validate(payload)
    expected = [payload]

    assert normalize_turn_input(image) == expected
    assert normalize_turn_input(image.root) == expected
    assert normalize_turn_input(protocol.UserInput(image)) == expected


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


def test_parse_notification_rejects_malformed_known_methods_in_non_strict_mode() -> None:
    with pytest.raises(AppServerProtocolError, match="turn/completed"):
        parse_notification(
            {"method": "turn/completed", "params": {"bad": True}},
            strict=False,
        )


def test_parse_server_request_allows_generic_unknown_methods_in_non_strict_mode() -> None:
    parsed = parse_server_request(
        {"id": "req-1", "method": "custom/request", "params": {"ok": True}},
        strict=False,
    )

    assert parsed == GenericServerRequest(id="req-1", method="custom/request", params={"ok": True})
    assert method_name(parsed) == "custom/request"
    assert request_id(parsed) == "req-1"


def test_parse_server_request_rejects_malformed_known_methods_in_non_strict_mode() -> None:
    with pytest.raises(AppServerProtocolError, match="item/tool/call"):
        parse_server_request(
            {"id": "req-1", "method": "item/tool/call", "params": {"bad": True}},
            strict=False,
        )


def test_parse_server_request_handles_permissions_approval_request() -> None:
    parsed = parse_server_request(
        {
            "id": "req-1",
            "method": "item/permissions/requestApproval",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "itemId": "item-1",
                "cwd": "/repo",
                "permissions": {
                    "network": {"enabled": True},
                    "fileSystem": {"read": ["/repo"], "write": ["/tmp/out"]},
                },
                "reason": "Tool requested additional access.",
                "startedAtMs": 1_714_000_000_000,
            },
        },
        strict=True,
    )

    assert isinstance(parsed, protocol.ItemPermissionsRequestApprovalRequest)
    assert method_name(parsed) == "item/permissions/requestApproval"
    assert request_id(parsed) == "req-1"
    assert parsed.params.permissions.network is not None
    assert parsed.params.permissions.network.enabled is True


@pytest.mark.parametrize("mode", ["openai/form", "openaiForm"])
def test_parse_server_request_preserves_openai_elicitation_schema(mode: str) -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    parsed = parse_server_request(
        {
            "id": "request-1",
            "method": "mcpServer/elicitation/request",
            "params": {
                "threadId": "thread-1",
                "serverName": "example",
                "mode": mode,
                "message": "Provide an answer",
                "requestedSchema": schema,
            },
        },
        strict=True,
    )

    assert isinstance(parsed, protocol.McpServerElicitationRequestRequest)
    assert parsed.params.root.mode == mode
    assert parsed.params.model_dump(mode="json")["requestedSchema"] == schema


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
                "completedAtMs": 1_714_000_000_000,
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


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"type": "amazonBedrock", "usesCodexManagedCredentials": True}, "amazonBedrock"),
        ({"type": "gcp"}, "gcp"),
    ],
)
def test_account_read_result_accepts_cloud_provider_accounts(
    payload: dict[str, object], expected_type: str
) -> None:
    result = parse_result(
        {"account": payload, "requiresOpenaiAuth": False},
        AccountReadResult,
    )

    assert result.account is not None
    account_type = result.account.type
    assert getattr(account_type, "root", account_type) == expected_type


def test_initialize_options_send_required_human_approval_capability() -> None:
    params = AppServerInitializeOptions(
        client_info=AppServerClientInfo(name="test", version="1"),
        experimental_api=True,
        required_human_approval=True,
    ).to_params()

    assert params["capabilities"] == {"experimentalApi": True, "requiredHumanApproval": True}


def test_options_forward_codex_0_167_protocol_fields() -> None:
    thread_list = AppServerThreadListOptions(
        attached_to_thread_id="thr-1", excluded_thread_ids=["thr-2"]
    ).to_params()
    fork = AppServerThreadForkOptions(
        attach_to_source=True,
        ephemeral=True,
        experimental_disable_prediction_mcp=True,
        experimental_prediction_mode=True,
    ).to_params(thread_id="thr-1")
    turn = AppServerTurnOptions(
        cyber_access_program=protocol.CyberAccessProgram("standard"),
        parent_turn_id="turn-1",
        responsesapi_client_metadata_patch={"trace_id": "trace-1"},
        root_turn_id="turn-0",
    ).to_params(thread_id="thr-1", input=[])

    assert thread_list.attachedToThreadId == "thr-1"
    assert thread_list.excludedThreadIds == ["thr-2"]
    assert fork.attachToSource is True
    assert fork.experimentalDisablePredictionMcp is True
    assert fork.experimentalPredictionMode is True
    assert turn.cyberAccessProgram == protocol.CyberAccessProgram("standard")
    assert turn.parentTurnId == "turn-1"
    assert turn.responsesapiClientMetadataPatch == {"trace_id": "trace-1"}
    assert turn.rootTurnId == "turn-0"


def _model_payload(**overrides: object) -> dict[str, object]:
    return {
        "defaultReasoningEffort": "low",
        "description": "Test model",
        "displayName": "Test",
        "hidden": False,
        "id": "test-model",
        "isDefault": True,
        "model": "test-model",
        "supportedReasoningEfforts": [],
        **overrides,
    }


def test_model_info_accepts_audio_input_modality() -> None:
    model = parse_result(_model_payload(inputModalities=["text", "audio"]), ModelInfo)

    assert model.input_modalities == ["text", "audio"]


def test_model_info_keeps_service_tiers() -> None:
    model = parse_result(_model_payload(serviceTiers=[], defaultServiceTier="fast"), ModelInfo)

    assert model.service_tiers == []
    assert model.default_service_tier == "fast"


def test_config_read_accepts_multiple_forced_workspaces() -> None:
    result = parse_result(
        {"config": {"forced_chatgpt_workspace_id": ["a", "b"]}, "origins": {}},
        ConfigReadResult,
    )

    assert result.config.forced_chatgpt_workspace_id == ["a", "b"]


def test_account_read_accepts_chatgpt_account_without_email() -> None:
    result = parse_result(
        {
            "account": {"type": "chatgpt", "email": None, "planType": "plus"},
            "requiresOpenaiAuth": False,
        },
        AccountReadResult,
    )

    assert isinstance(result.account, ChatGptAccountInfo)
    assert result.account.email is None


def test_serialize_value_sends_explicit_null_for_clearable_fields() -> None:
    params = protocol.ThreadMetadataUpdateParams(
        threadId="thread-1",
        gitInfo=protocol.ThreadMetadataGitInfoUpdateParams(branch=None, sha="abc"),
    )

    assert serialize_value(params) == {
        "threadId": "thread-1",
        "gitInfo": {"branch": None, "sha": "abc"},
    }


def test_serialize_value_omits_explicit_none_on_fields_that_reject_null() -> None:
    assert ("AppsListParams", "forceRefetch") in protocol.NON_NULLABLE_OPTIONAL_FIELDS

    assert serialize_value(protocol.AppsListParams(forceRefetch=None, limit=5)) == {"limit": 5}


def test_serialize_value_keeps_stripping_none_on_non_protocol_models() -> None:
    class Payload(BaseModel):
        note: str | None = None

    assert serialize_value(Payload(note=None)) == {}


def test_non_nullable_optional_fields_resolve_to_generated_fields() -> None:
    for model_name, field_name in protocol.NON_NULLABLE_OPTIONAL_FIELDS:
        model = getattr(protocol, model_name)
        wire_names = {field.alias or name for name, field in model.model_fields.items()}
        assert field_name in wire_names, (model_name, field_name)
