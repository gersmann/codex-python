from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codex.protocol import types as protocol

type CodexConfigValue = (
    str | int | float | bool | list["CodexConfigValue"] | dict[str, "CodexConfigValue"]
)
type CodexConfigObject = dict[str, CodexConfigValue]


class CodexConfig(BaseModel):
    """Typed top-level Codex config shape with forward-compatible extra keys."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, CodexConfigValue]

    analytics: CodexConfigObject | None = Field(
        default=None,
        description="Open-ended analytics configuration subtree.",
    )
    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Default approval policy for new turns and commands.",
    )
    compact_prompt: str | None = Field(
        default=None,
        description="Prompt text used when the app-server compacts thread history.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Default developer instructions applied to new turns.",
    )
    forced_chatgpt_workspace_id: str | None = Field(
        default=None,
        description="Workspace identifier to force for ChatGPT-managed auth flows.",
    )
    forced_login_method: Literal["chatgpt", "api"] | None = Field(
        default=None,
        description="Force Codex auth to ChatGPT or API-key mode.",
    )
    instructions: str | None = Field(
        default=None,
        description="Default user-visible instructions prepended to new conversations.",
    )
    model: str | None = Field(
        default=None,
        description="Default model id used when threads or turns do not override it.",
    )
    model_auto_compact_token_limit: int | None = Field(
        default=None,
        description="Token threshold that triggers automatic thread compaction.",
    )
    model_context_window: int | None = Field(
        default=None,
        description="Context window size override for the configured model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Default model provider name.",
    )
    model_reasoning_effort: protocol.ReasoningEffort | None = Field(
        default=None,
        description="Default reasoning effort for turns that do not override it.",
    )
    model_reasoning_summary: protocol.ReasoningSummary | None = Field(
        default=None,
        description="Default reasoning-summary behavior for supported models.",
    )
    model_verbosity: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description="Default verbosity for supported models.",
    )
    profile: str | None = Field(
        default=None,
        description="Name of the active Codex profile.",
    )
    profiles: CodexConfigObject | None = Field(
        default_factory=dict,
        description="Open-ended profile definitions keyed by profile name.",
    )
    review_model: str | None = Field(
        default=None,
        description="Model override used for review flows.",
    )
    sandbox_mode: protocol.SandboxMode | None = Field(
        default=None,
        description="Default sandbox mode for new threads and turns.",
    )
    sandbox_workspace_write: CodexConfigObject | None = Field(
        default=None,
        description="Open-ended workspace-write sandbox configuration subtree.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Default service tier for requests that do not override it.",
    )
    tools: CodexConfigObject | None = Field(
        default=None,
        description="Open-ended tool configuration subtree.",
    )
    web_search: Literal["disabled", "cached", "live"] | None = Field(
        default=None,
        description="Default web-search mode.",
    )
