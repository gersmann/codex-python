from __future__ import annotations

from pathlib import Path


def test_generated_protocol_types_do_not_use_legacy_conint() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert " conint" not in content
    assert "conint(" not in content


def test_generated_protocol_types_include_v2_response_models() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert "class ModelListResponse(BaseModel)" in content
    assert "class SkillsListResponse(BaseModel)" in content
    assert "class ConfigReadResponse(BaseModel)" in content
    assert "class GetAccountResponse(BaseModel)" in content
    assert "class CommandExecResponse(BaseModel)" in content
    assert "class ThreadStartResponse(BaseModel)" in content
    assert "class WindowsSandboxSetupStartResponse(BaseModel)" in content
    assert "class McpAuthStatus" in content
    assert "class Resource(BaseModel)" in content
    assert "class ResourceTemplate(BaseModel)" in content
    assert "class Tool(BaseModel)" in content
    assert "class McpServerStatus(BaseModel)" in content
    assert "class ListMcpServerStatusResponse(BaseModel)" in content


def test_generated_protocol_types_expose_union_rootmodel_value_aliases() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert "type ServerNotificationValue = (" in content
    assert "type ServerRequestValue = (" in content
    assert "type ClientRequestValue = (" in content
    assert (
        "class ServerNotification(RootModel):\n"
        "    root: Annotated[\n"
        "        ServerNotificationValue,"
    ) in content
