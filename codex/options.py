from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ApprovalMode = Literal["never", "on-request", "on-failure", "untrusted"]
SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]


@dataclass(slots=True, frozen=True)
class CodexOptions:
    codex_path_override: str | None = None
    base_url: str | None = None
    api_key: str | None = None


@dataclass(slots=True, frozen=True)
class ThreadOptions:
    model: str | None = None
    sandbox_mode: SandboxMode | None = None
    working_directory: str | None = None
    skip_git_repo_check: bool = False


@dataclass(slots=True, frozen=True)
class TurnOptions:
    output_schema: dict[str, object] | None = None
