from __future__ import annotations

from pathlib import Path


def test_generated_protocol_types_do_not_use_legacy_conint() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert " conint" not in content
    assert "conint(" not in content


def test_generated_protocol_types_include_mcp_status_response_models() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert "class McpAuthStatus" in content
    assert "class Resource(BaseModel)" in content
    assert "class ResourceTemplate(BaseModel)" in content
    assert "class Tool(BaseModel)" in content
    assert "class McpServerStatus(BaseModel)" in content
    assert "class ListMcpServerStatusResponse(BaseModel)" in content
