"""Public option models for the high-level `Codex` client."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from codex._config_types import CodexConfigObject, CodexConfigValue
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

    codex_path_override: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    config: CodexConfigObject | None = None
    env: dict[str, str] | None = None
    analytics_default_enabled: bool = False

    def to_app_server_options(self) -> AppServerProcessOptions:
        return AppServerProcessOptions.model_validate(self.model_dump(mode="python"))


class ThreadStartOptions(_CodexOptionsModel):
    """Thread creation options for the high-level `Codex` client."""

    approval_policy: protocol.AskForApproval | None = None
    base_instructions: str | None = None
    config: CodexConfigObject | None = None
    cwd: str | None = None
    developer_instructions: str | None = None
    dynamic_tools: list[protocol.DynamicToolSpec] | None = None
    ephemeral: bool | None = None
    experimental_raw_events: bool | None = None
    mock_experimental_field: str | None = None
    model: str | None = None
    model_provider: str | None = None
    persist_extended_history: bool | None = None
    personality: protocol.Personality | None = None
    sandbox: protocol.SandboxMode | None = None
    service_name: str | None = None
    service_tier: protocol.ServiceTier | None = None

    def to_app_server_options(self) -> AppServerThreadStartOptions:
        return AppServerThreadStartOptions.model_validate(self.model_dump(mode="python"))


class ThreadResumeOptions(_CodexOptionsModel):
    """Thread resume options for the high-level `Codex` client."""

    approval_policy: protocol.AskForApproval | None = None
    base_instructions: str | None = None
    config: CodexConfigObject | None = None
    cwd: str | None = None
    developer_instructions: str | None = None
    history: list[protocol.ResponseItem] | None = None
    model: str | None = None
    model_provider: str | None = None
    path: str | None = None
    persist_extended_history: bool | None = None
    personality: protocol.Personality | None = None
    sandbox: protocol.SandboxMode | None = None
    service_tier: protocol.ServiceTier | None = None

    def to_app_server_options(self) -> AppServerThreadResumeOptions:
        return AppServerThreadResumeOptions.model_validate(self.model_dump(mode="python"))


class TurnOptions(_CodexOptionsModel):
    """Turn execution options for the high-level `Codex` client."""

    approval_policy: protocol.AskForApproval | None = None
    collaboration_mode: protocol.CollaborationMode | None = None
    cwd: str | None = None
    effort: protocol.ReasoningEffort | None = None
    model: str | None = None
    output_schema: OutputSchemaInput | None = None
    personality: protocol.Personality | None = None
    sandbox_policy: protocol.SandboxPolicy | None = None
    service_tier: protocol.ServiceTier | None = None
    summary: protocol.ReasoningSummary | None = None

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
    "CodexConfigValue",
    "CodexConfigObject",
    "SupportsIsSet",
    "SupportsAborted",
    "CancelSignal",
]
