from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ApprovalMode = Literal["never", "on-request", "on-failure", "untrusted"]
SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]
ModelReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh"]
WebSearchMode = Literal["disabled", "cached", "live"]

type CodexConfigValue = (
    str | int | float | bool | list["CodexConfigValue"] | dict[str, "CodexConfigValue"]
)
type CodexConfigObject = dict[str, CodexConfigValue]


@runtime_checkable
class SupportsIsSet(Protocol):
    def is_set(self) -> bool: ...


@runtime_checkable
class SupportsAborted(Protocol):
    @property
    def aborted(self) -> bool: ...


type CancelSignal = SupportsIsSet | SupportsAborted


@dataclass(slots=True, frozen=True)
class CodexOptions:
    codex_path_override: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    config: CodexConfigObject | None = None
    env: dict[str, str] | None = None


@dataclass(slots=True, frozen=True)
class ThreadOptions:
    model: str | None = None
    sandbox_mode: SandboxMode | None = None
    working_directory: str | None = None
    skip_git_repo_check: bool = False
    model_reasoning_effort: ModelReasoningEffort | None = None
    network_access_enabled: bool | None = None
    web_search_mode: WebSearchMode | None = None
    web_search_enabled: bool | None = None
    approval_policy: ApprovalMode | None = None
    additional_directories: list[str] | None = None


@dataclass(slots=True, frozen=True)
class TurnOptions:
    output_schema: dict[str, object] | None = None
    signal: CancelSignal | None = None
