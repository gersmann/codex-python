from __future__ import annotations

from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field


class ApprovalPolicy(str, Enum):
    """Approval policy for executing shell commands.

    Matches Rust enum `AskForApproval` (serde kebab-case):
    - "untrusted": auto-approve safe read-only commands, ask otherwise
    - "on-failure": sandbox by default; ask only if the sandboxed run fails
    - "on-request": model decides (default)
    - "never": never ask the user
    """

    UNTRUSTED = "untrusted"
    ON_FAILURE = "on-failure"
    ON_REQUEST = "on-request"
    NEVER = "never"


class SandboxMode(str, Enum):
    """High-level sandbox mode override.

    Matches Rust enum `SandboxMode` (serde kebab-case):
    - "read-only"
    - "workspace-write"
    - "danger-full-access"
    """

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


class CodexConfig(BaseModel):
    """Configuration overrides for Codex.

    This mirrors `codex_core::config::ConfigOverrides` and is intentionally
    conservative: only values present (not None) are passed to the native core.
    """

    # Model selection
    model: str | None = Field(default=None, description="Model slug, e.g. 'gpt-5' or 'o3'.")
    model_provider: str | None = Field(
        default=None, description="Provider key from config, e.g. 'openai'."
    )

    # Safety/Execution
    approval_policy: ApprovalPolicy | None = Field(default=None)
    sandbox_mode: SandboxMode | None = Field(default=None)

    # Environment
    cwd: str | None = Field(default=None, description="Working directory for the session.")
    config_profile: str | None = Field(
        default=None, description="Config profile key to use (from profiles.*)."
    )
    codex_linux_sandbox_exe: str | None = Field(
        default=None, description="Absolute path to codex-linux-sandbox (Linux only)."
    )

    # UX / features
    base_instructions: str | None = Field(default=None, description="Override base instructions.")
    include_plan_tool: bool | None = Field(default=None)
    include_apply_patch_tool: bool | None = Field(default=None)
    include_view_image_tool: bool | None = Field(default=None)
    show_raw_agent_reasoning: bool | None = Field(default=None)
    tools_web_search_request: bool | None = Field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Return overrides as a plain dict with None values removed.

        Enum fields are emitted as their string values.
        """
        return cast(dict[str, Any], self.model_dump(exclude_none=True))

    # Pydantic v2 config. `use_enum_values=True` ensures enums dump as strings.
    # Place at end of class, extra='allow' per style.
    model_config = ConfigDict(extra="allow", validate_assignment=True, use_enum_values=True)
