from pathlib import Path

import pytest

# Skip this module entirely if the native extension is unavailable
pytest.importorskip("codex_native", reason="native extension not installed")

from codex.config import ApprovalPolicy, CodexConfig, SandboxMode, ToolsConfig  # noqa: E402
from codex.native import preview_config  # noqa: E402


def test_preview_config_minimal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / ".codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    cfg = CodexConfig(
        model="gpt-5",
        model_provider="openai",
        approval_policy=ApprovalPolicy.ON_REQUEST,
        sandbox_mode=SandboxMode.WORKSPACE_WRITE,
        cwd=str(tmp_path / "proj"),
    )
    out = preview_config(config_overrides=cfg.to_dict(), load_default_config=False)

    assert out["model"] == "gpt-5"
    assert out["model_provider_id"] == "openai"
    assert out["approval_policy"] == "on-request"
    assert out["sandbox_mode"] == "workspace-write"
    assert out["cwd"].endswith("proj")


def test_preview_config_feature_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    codex_home = tmp_path / ".codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    cfg = CodexConfig(
        include_apply_patch_tool=True,
        include_plan_tool=False,
        include_view_image_tool=False,
        show_raw_agent_reasoning=True,
        tools=ToolsConfig(web_search=True),
    )
    out = preview_config(config_overrides=cfg.to_dict(), load_default_config=False)

    assert out["include_apply_patch_tool"] is True
    assert out["include_plan_tool"] is False
    assert out["include_view_image_tool"] is False
    assert out["show_raw_agent_reasoning"] is True
    assert out["tools_web_search_request"] is True


def test_preview_config_tools_web_search_nested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = tmp_path / ".codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    # Use nested tools.web_search enabling via extras to ensure Python -> Rust CLI overrides path works
    cfg = CodexConfig(tools={"web_search": True})
    out = preview_config(config_overrides=cfg.to_dict(), load_default_config=False)

    assert out["tools_web_search_request"] is True
