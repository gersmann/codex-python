from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ConfigDict as PydanticConfigDict
from pydantic.alias_generators import to_camel

from codex._config_types import CodexConfigObject, CodexConfigValue
from codex.protocol import types as protocol


class AppServerResultModel(BaseModel):
    model_config = PydanticConfigDict(alias_generator=to_camel, populate_by_name=True)


class EmptyResult(AppServerResultModel):
    pass


class InitializeResult(AppServerResultModel):
    user_agent: str


class ThreadResult(AppServerResultModel):
    thread: protocol.Thread


class ThreadListResult(AppServerResultModel):
    data: list[protocol.Thread]
    next_cursor: str | None = None


class LoadedThreadsResult(AppServerResultModel):
    data: list[str]


class TurnResult(AppServerResultModel):
    turn: protocol.Turn


class ReviewResult(AppServerResultModel):
    turn: protocol.Turn
    review_thread_id: str


class TurnIdResult(AppServerResultModel):
    turn_id: str


class ModelAvailabilityNux(AppServerResultModel):
    message: str


class ModelUpgradeInfo(AppServerResultModel):
    migration_markdown: str | None = None
    model: str
    model_link: str | None = None
    upgrade_copy: str | None = None


class ReasoningEffortOption(AppServerResultModel):
    description: str
    reasoning_effort: protocol.ReasoningEffort


DEFAULT_INPUT_MODALITIES: tuple[Literal["text", "image"], Literal["text", "image"]] = (
    "text",
    "image",
)


class ModelInfo(AppServerResultModel):
    availability_nux: ModelAvailabilityNux | None = None
    default_reasoning_effort: protocol.ReasoningEffort
    description: str
    display_name: str
    hidden: bool
    id: str
    input_modalities: list[Literal["text", "image"]] | None = Field(
        default_factory=lambda: list(DEFAULT_INPUT_MODALITIES)
    )
    is_default: bool
    model: str
    supported_reasoning_efforts: list[ReasoningEffortOption]
    supports_personality: bool | None = False
    upgrade: str | None = None
    upgrade_info: ModelUpgradeInfo | None = None


class ModelListResult(AppServerResultModel):
    data: list[ModelInfo]
    next_cursor: str | None = None


class AppListResult(AppServerResultModel):
    data: list[protocol.AppInfo]
    next_cursor: str | None = None


class SkillsListResult(AppServerResultModel):
    data: list[protocol.SkillsListEntry]


class SkillsConfigWriteResult(AppServerResultModel):
    effective_enabled: bool


class ApiKeyAccountInfo(AppServerResultModel):
    type: Literal["apiKey"]


class ChatGptAccountInfo(AppServerResultModel):
    email: str
    plan_type: protocol.PlanType
    type: Literal["chatgpt"]


class AccountReadResult(AppServerResultModel):
    account: ApiKeyAccountInfo | ChatGptAccountInfo | None = None
    requires_openai_auth: bool


class ApiKeyLoginResult(AppServerResultModel):
    type: Literal["apiKey"]


class ChatGptLoginResult(AppServerResultModel):
    auth_url: str
    login_id: str
    type: Literal["chatgpt"]


class ChatGptAuthTokensLoginResult(AppServerResultModel):
    type: Literal["chatgptAuthTokens"]


class AccountCancelLoginResult(AppServerResultModel):
    status: Literal["canceled", "notFound"]


class AccountRateLimitsResult(AppServerResultModel):
    rate_limits: protocol.RateLimitSnapshot
    rate_limits_by_limit_id: dict[str, protocol.RateLimitSnapshot] | None = None


class AppServerConfig(BaseModel):
    model_config = PydanticConfigDict(extra="allow")

    analytics: CodexConfigObject | None = None
    approval_policy: protocol.AskForApproval | None = None
    compact_prompt: str | None = None
    developer_instructions: str | None = None
    forced_chatgpt_workspace_id: str | None = None
    forced_login_method: Literal["chatgpt", "api"] | None = None
    instructions: str | None = None
    model: str | None = None
    model_auto_compact_token_limit: int | None = None
    model_context_window: int | None = None
    model_provider: str | None = None
    model_reasoning_effort: protocol.ReasoningEffort | None = None
    model_reasoning_summary: protocol.ReasoningSummary | None = None
    model_verbosity: Literal["low", "medium", "high"] | None = None
    profile: str | None = None
    profiles: CodexConfigObject | None = Field(default_factory=dict)
    review_model: str | None = None
    sandbox_mode: protocol.SandboxMode | None = None
    sandbox_workspace_write: CodexConfigObject | None = None
    service_tier: protocol.ServiceTier | None = None
    tools: CodexConfigObject | None = None
    web_search: Literal["disabled", "cached", "live"] | None = None


class ConfigLayerMetadata(AppServerResultModel):
    name: CodexConfigObject
    version: str


class ConfigLayer(AppServerResultModel):
    config: CodexConfigObject
    disabled_reason: str | None = None
    name: CodexConfigObject
    version: str


class OverriddenMetadata(AppServerResultModel):
    effective_value: CodexConfigValue
    message: str
    overriding_layer: ConfigLayerMetadata


class ConfigReadResult(AppServerResultModel):
    config: AppServerConfig
    layers: list[ConfigLayer] | None = None
    origins: dict[str, ConfigLayerMetadata]


class ConfigWriteResult(AppServerResultModel):
    file_path: str
    overridden_metadata: OverriddenMetadata | None = None
    status: Literal["ok", "okOverridden"]
    version: str


class ConfigRequirements(AppServerResultModel):
    allowed_approval_policies: list[protocol.AskForApproval] | None = None
    allowed_sandbox_modes: list[protocol.SandboxMode] | None = None
    allowed_web_search_modes: list[Literal["disabled", "cached", "live"]] | None = None
    enforce_residency: Literal["us"] | None = None
    feature_requirements: dict[str, bool] | None = None


class ConfigRequirementsReadResult(AppServerResultModel):
    requirements: ConfigRequirements | None = None


class McpServerStatus(AppServerResultModel):
    auth_status: protocol.McpAuthStatus
    name: str
    resource_templates: list[protocol.ResourceTemplate]
    resources: list[protocol.Resource]
    tools: dict[str, protocol.Tool]


class McpServerStatusListResult(AppServerResultModel):
    data: list[McpServerStatus]
    next_cursor: str | None = None


class McpServerOauthLoginResult(AppServerResultModel):
    authorization_url: str


class FeedbackUploadResult(AppServerResultModel):
    thread_id: str


class CommandExecResult(AppServerResultModel):
    exit_code: int
    stderr: str
    stdout: str


class ExternalAgentConfigDetectResult(AppServerResultModel):
    items: list[protocol.ExternalAgentConfigMigrationItem]


class WindowsSandboxSetupStartResult(AppServerResultModel):
    started: bool


class GenericNotification(AppServerResultModel):
    method: str
    params: dict[str, object] = Field(default_factory=dict)


class GenericServerRequest(AppServerResultModel):
    id: str | int
    method: str
    params: dict[str, object] = Field(default_factory=dict)
