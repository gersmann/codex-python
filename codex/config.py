from __future__ import annotations

from enum import Enum
from typing import Any, cast

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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


class HistoryPersistence(str, Enum):
    SAVE_ALL = "save-all"
    NONE = "none"


class HistoryConfig(BaseModel):
    persistence: HistoryPersistence | None = None
    max_bytes: int | None = None

    model_config = ConfigDict(extra="allow")


class SandboxWorkspaceWrite(BaseModel):
    """Fine‑grained settings for WorkspaceWrite sandbox mode.

    Mirrors `core::config_types::SandboxWorkspaceWrite`.
    - writable_roots: extra directories the agent may write to in addition to CWD.
    - network_access: whether outbound network is allowed when in WorkspaceWrite.
    - exclude_tmpdir_env_var: if true, do NOT auto‑include $TMPDIR as writable.
    - exclude_slash_tmp: if true, do NOT auto‑include /tmp as writable.
    """

    writable_roots: list[str] | None = None
    network_access: bool | None = None
    exclude_tmpdir_env_var: bool | None = None
    exclude_slash_tmp: bool | None = None

    model_config = ConfigDict(extra="allow")


class ShellEnvironmentPolicyInherit(str, Enum):
    """Baseline environment to inherit for shell/local_shell tool processes."""

    CORE = "core"
    ALL = "all"
    NONE = "none"


class ShellEnvironmentPolicy(BaseModel):
    """Policy for constructing env vars for spawned commands.

    Matches `core::config_types::ShellEnvironmentPolicyToml`.
    The build algorithm is: start from `inherit`, optionally filter by default
    excludes, apply `exclude`, insert `set`, then filter by `include_only`.

    - inherit: one of core/all/none; starting env for the child process.
    - ignore_default_excludes: if true, do NOT auto‑filter *KEY*/*TOKEN* names.
    - exclude: regex/wildmatch patterns to drop from the env.
    - set: explicit key/value pairs to add to the env.
    - include_only: allow‑list patterns; if set, drop everything else.
    - experimental_use_profile: if true, run via the user's shell profile.
    """

    inherit: ShellEnvironmentPolicyInherit | None = None
    ignore_default_excludes: bool | None = None
    exclude: list[str] | None = None
    # Key is `set` in TOML; Python attribute name is allowed.
    set: dict[str, str] | None = None
    include_only: list[str] | None = None
    experimental_use_profile: bool | None = None

    model_config = ConfigDict(extra="allow")


class McpServerConfig(BaseModel):
    command: str
    args: list[str] | None = None
    env: dict[str, str] | None = None
    startup_timeout_ms: int | None = None

    model_config = ConfigDict(extra="allow")


class WireApi(str, Enum):
    CHAT = "chat"
    RESPONSES = "responses"


class ModelProviderConfig(BaseModel):
    """Defines an OpenAI‑compatible provider entry.

    - wire_api: `responses` for /v1/responses, `chat` for /v1/chat/completions.
    - env_key: environment variable containing an API key (if required).
    - env_key_instructions: hint shown when the key is missing.
    - request/stream_*: retry and idle timeout tuning.
    - requires_openai_auth: if true, prefer ChatGPT/OAuth auth instead of API key.
    """

    name: str | None = None
    base_url: str | None = None
    env_key: str | None = None
    env_key_instructions: str | None = None
    wire_api: WireApi | None = None
    query_params: dict[str, str] | None = None
    http_headers: dict[str, str] | None = None
    env_http_headers: dict[str, str] | None = None
    request_max_retries: int | None = None
    stream_max_retries: int | None = None
    stream_idle_timeout_ms: int | None = None
    requires_openai_auth: bool | None = None

    model_config = ConfigDict(extra="allow")


class FileOpener(str, Enum):
    VSCODE = "vscode"
    VSCODE_INSIDERS = "vscode-insiders"
    WINDSURF = "windsurf"
    CURSOR = "cursor"
    NONE = "none"


class ReasoningEffort(str, Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningSummary(str, Enum):
    AUTO = "auto"
    CONCISE = "concise"
    DETAILED = "detailed"
    NONE = "none"


class ReasoningSummaryFormat(str, Enum):
    NONE = "none"
    EXPERIMENTAL = "experimental"


class Verbosity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolsConfig(BaseModel):
    # Accept either "web_search" or legacy alias "web_search_request" on input
    web_search: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("web_search", "web_search_request"),
        description="Enable builtin web search tool (alias: web_search_request)",
    )
    # Also expose view_image knob (defaults handled in Rust)
    view_image: bool | None = Field(
        default=None, description="Enable tool to attach local images to context"
    )

    model_config = ConfigDict(extra="allow")


class ProfileConfig(BaseModel):
    model: str | None = None
    model_provider: str | None = None
    approval_policy: ApprovalPolicy | None = None
    model_reasoning_effort: ReasoningEffort | None = None
    model_reasoning_summary: ReasoningSummary | None = None
    model_verbosity: Verbosity | None = None
    chatgpt_base_url: str | None = None
    experimental_instructions_file: str | None = None

    model_config = ConfigDict(extra="allow")


class ProjectConfig(BaseModel):
    trust_level: str | None = Field(
        default=None, description='Only "trusted" is recognized by the core.'
    )

    model_config = ConfigDict(extra="allow")


class PreferredAuthMethod(str, Enum):
    CHATGPT = "chatgpt"
    APIKEY = "apikey"


class CodexConfig(BaseModel):
    """Configuration overrides for Codex.

    This mirrors `codex_core::config::ConfigOverrides` and is intentionally
    conservative: only values present (not None) are passed to the native core.
    """

    # Model selection
    model: str | None = Field(default=None, description="Model slug, e.g. 'gpt-5' or 'o3'.")
    review_model: str | None = Field(
        default=None,
        description="Preferred model when running /review features (if supported).",
    )
    model_provider: str | None = Field(
        default=None, description="Provider key from config, e.g. 'openai'."
    )

    # Safety/Execution
    approval_policy: ApprovalPolicy | None = Field(default=None)
    sandbox_mode: SandboxMode | None = Field(default=None)
    sandbox_workspace_write: SandboxWorkspaceWrite | None = None

    # Environment
    cwd: str | None = Field(default=None, description="Working directory for the session.")
    config_profile: str | None = Field(
        default=None, description="Config profile key to use (from profiles.*)."
    )
    codex_linux_sandbox_exe: str | None = Field(
        default=None, description="Absolute path to codex-linux-sandbox (Linux only)."
    )
    shell_environment_policy: ShellEnvironmentPolicy | None = Field(
        default=None, description="How child process env vars are constructed for shell tools."
    )

    # UX / features
    base_instructions: str | None = Field(default=None, description="Override base instructions.")
    include_apply_patch_tool: bool | None = Field(default=None)
    include_view_image_tool: bool | None = Field(default=None)
    show_raw_agent_reasoning: bool | None = Field(default=None)

    # Model/runtime tuning
    model_context_window: int | None = None
    model_max_output_tokens: int | None = None
    model_auto_compact_token_limit: int | None = Field(
        default=None,
        description="Token threshold to auto‑compact history; if unset, model default applies.",
    )
    model_reasoning_effort: ReasoningEffort | None = None
    model_reasoning_summary: ReasoningSummary | None = None
    model_verbosity: Verbosity | None = None
    model_supports_reasoning_summaries: bool | None = None
    model_reasoning_summary_format: ReasoningSummaryFormat | None = None

    # Auth/UI options
    hide_agent_reasoning: bool | None = None
    chatgpt_base_url: str | None = None
    preferred_auth_method: PreferredAuthMethod | None = None
    file_opener: FileOpener | None = None
    disable_paste_burst: bool | None = Field(
        default=None,
        description="If true, disables paste burst buffering in interactive UIs.",
    )

    # Config file composed sections
    history: HistoryConfig | None = None
    tui: dict[str, Any] | None = None
    notify: list[str] | None = None
    instructions: str | None = Field(
        default=None,
        description="Ignored by core; prefer AGENTS.md or experimental_instructions_file.",
    )
    mcp_servers: dict[str, McpServerConfig] | None = None
    model_providers: dict[str, ModelProviderConfig] | None = None
    project_doc_max_bytes: int | None = None
    profile: str | None = None
    profiles: dict[str, ProfileConfig] | None = None
    # Accept either a structured ToolsConfig or a plain mapping (common in tests/CLI overrides)
    tools: ToolsConfig | dict[str, Any] | None = None
    projects: dict[str, ProjectConfig] | None = None

    # Experimental / internal
    experimental_resume: str | None = None
    experimental_instructions_file: str | None = None
    experimental_use_exec_command_tool: bool | None = Field(
        default=None,
        description="Use experimental streamable exec tool in place of legacy shell tool.",
    )
    experimental_use_unified_exec_tool: bool | None = Field(
        default=None, description="Use unified exec tool for all command invocations."
    )
    responses_originator_header_internal_override: str | None = None
    disable_response_storage: bool | None = Field(
        default=None, description="Accepted in some clients; ignored by core."
    )
    # Typed override (maps to core ConfigOverrides.tools_web_search_request)
    tools_web_search_request: bool | None = Field(
        default=None, description="Force‑enable web_search tool without reading config file."
    )

    def to_dict(self) -> dict[str, Any]:
        """Return overrides as a plain dict with None values removed.

        Enum fields are emitted as their string values.
        """
        return cast(dict[str, Any], self.model_dump(exclude_none=True))

    # Pydantic v2 config. `use_enum_values=True` ensures enums dump as strings.
    # Place at end of class, extra='allow' per style.
    model_config = ConfigDict(extra="allow", validate_assignment=True, use_enum_values=True)
