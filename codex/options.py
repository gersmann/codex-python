"""Public option models for the high-level `Codex` client."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from codex._config_types import CodexConfig, CodexConfigObject, CodexConfigValue
from codex.app_server.options import (
    AppServerProcessOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnOptions,
)
from codex.output_schema import OutputSchemaInput
from codex.protocol import types as protocol


class _CodexOptionsModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class CodexOptions(_CodexOptionsModel):
    """Process options for the high-level `Codex` client."""

    codex_path_override: str | None = Field(
        default=None,
        description="Forwarded to AppServerProcessOptions.codex_path_override.",
    )
    base_url: str | None = Field(
        default=None,
        description="Forwarded to AppServerProcessOptions.base_url.",
    )
    api_key: str | None = Field(
        default=None,
        description=(
            "Forwarded to AppServerProcessOptions.api_key and used for app-server account login "
            "when the high-level Codex client connects."
        ),
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Forwarded to AppServerProcessOptions.config.",
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Forwarded to AppServerProcessOptions.env.",
    )

    def to_app_server_options(self) -> AppServerProcessOptions:
        return AppServerProcessOptions.model_validate(self.model_dump(mode="python"))


class ThreadStartOptions(_CodexOptionsModel):
    """Thread creation options for the high-level `Codex` client."""

    allow_provider_model_fallback: bool | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.allow_provider_model_fallback.",
    )
    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.approval_policy.",
    )
    base_instructions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.base_instructions.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.config.",
    )
    cwd: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.cwd.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.developer_instructions.",
    )
    dynamic_tools: list[protocol.DynamicToolSpec] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.dynamic_tools.",
    )
    environments: list[protocol.TurnEnvironmentParams] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.environments.",
    )
    ephemeral: bool | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.ephemeral.",
    )
    experimental_raw_events: bool | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.experimental_raw_events.",
    )
    history_mode: protocol.ThreadHistoryMode | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.history_mode.",
    )
    mock_experimental_field: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.mock_experimental_field.",
    )
    model: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.model_provider.",
    )
    permissions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.permissions.",
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.personality.",
    )
    runtime_workspace_roots: list[protocol.AbsolutePathBuf] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.runtime_workspace_roots.",
    )
    sandbox: protocol.SandboxMode | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.sandbox.",
    )
    selected_capability_roots: list[protocol.SelectedCapabilityRoot] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.selected_capability_roots.",
    )
    service_name: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.service_name.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.service_tier.",
    )
    thread_source: protocol.ThreadSource | None = Field(
        default=None,
        description="Forwarded to AppServerThreadStartOptions.thread_source.",
    )

    def to_app_server_options(self) -> AppServerThreadStartOptions:
        return AppServerThreadStartOptions.model_validate(self.model_dump(mode="python"))


class ThreadResumeOptions(_CodexOptionsModel):
    """Thread resume options for the high-level `Codex` client."""

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.approval_policy.",
    )
    base_instructions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.base_instructions.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.config.",
    )
    cwd: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.cwd.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.developer_instructions.",
    )
    exclude_turns: bool | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.exclude_turns.",
    )
    history: list[protocol.ResponseItem] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.history.",
    )
    initial_turns_page: protocol.ThreadResumeInitialTurnsPageParams | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.initial_turns_page.",
    )
    model: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.model_provider.",
    )
    path: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.path.",
    )
    permissions: str | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.permissions.",
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.personality.",
    )
    runtime_workspace_roots: list[protocol.AbsolutePathBuf] | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.runtime_workspace_roots.",
    )
    sandbox: protocol.SandboxMode | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.sandbox.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Forwarded to AppServerThreadResumeOptions.service_tier.",
    )

    def to_app_server_options(self) -> AppServerThreadResumeOptions:
        return AppServerThreadResumeOptions.model_validate(self.model_dump(mode="python"))


class TurnOptions(_CodexOptionsModel):
    """Turn execution options for the high-level `Codex` client."""

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.approval_policy.",
    )
    additional_context: dict[str, protocol.AdditionalContextEntry] | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.additional_context.",
    )
    client_user_message_id: str | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.client_user_message_id.",
    )
    collaboration_mode: protocol.CollaborationMode | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.collaboration_mode.",
    )
    cwd: str | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.cwd.",
    )
    environments: list[protocol.TurnEnvironmentParams] | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.environments.",
    )
    effort: protocol.ReasoningEffort | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.effort.",
    )
    model: str | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.model.",
    )
    output_schema: OutputSchemaInput | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.output_schema.",
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.personality.",
    )
    permissions: str | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.permissions.",
    )
    runtime_workspace_roots: list[protocol.AbsolutePathBuf] | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.runtime_workspace_roots.",
    )
    sandbox_policy: protocol.SandboxPolicy | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.sandbox_policy.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.service_tier.",
    )
    summary: protocol.ReasoningSummary | None = Field(
        default=None,
        description="Forwarded to AppServerTurnOptions.summary.",
    )

    def to_app_server_options(self) -> AppServerTurnOptions:
        return AppServerTurnOptions.model_validate(self.model_dump(mode="python"))


@runtime_checkable
class SupportsIsSet(Protocol):
    def is_set(self) -> bool: ...


@runtime_checkable
class SupportsAborted(Protocol):
    @property
    def aborted(self) -> bool: ...


type CancelSignal = SupportsIsSet | SupportsAborted

__all__ = [
    "CodexOptions",
    "ThreadStartOptions",
    "ThreadResumeOptions",
    "TurnOptions",
    "CodexConfig",
    "CodexConfigValue",
    "CodexConfigObject",
    "SupportsIsSet",
    "SupportsAborted",
    "CancelSignal",
]
