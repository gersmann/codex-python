# GENERATED CODE! DO NOT MODIFY BY HAND!
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from pydantic.config import ConfigDict


class AddConversationListenerParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId


class AddConversationSubscriptionResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscriptionId: str


class AgentMessageDeltaEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: str


class AgentMessageEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


class AgentReasoningDeltaEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: str


class AgentReasoningEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class AgentReasoningRawContentDeltaEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: str


class AgentReasoningRawContentEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class AgentReasoningSectionBreakEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class Annotations_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ApplyPatchApprovalParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: ConversationId
    call_id: str
    file_changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None


class ApplyPatchApprovalRequestEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None


class ApplyPatchApprovalResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ReviewDecision


class ArchiveConversationParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    rolloutPath: str


class ArchiveConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class AudioContent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: str
    mimeType: str
    type: str


class AuthStatusChangeNotification_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authMethod: AuthMode | None = None


class BackgroundEventEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


class BlobResourceContents_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blob: str
    uri: str


class CallToolResult_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: list[ContentBlock]


class CancelLoginChatGptParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loginId: str


class CancelLoginChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ClientRequest_NewConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["newConversation"]
    id: RequestId
    params: NewConversationParams


class ClientRequest_ListConversations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["listConversations"]
    id: RequestId
    params: ListConversationsParams


class ClientRequest_ResumeConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["resumeConversation"]
    id: RequestId
    params: ResumeConversationParams


class ClientRequest_ArchiveConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["archiveConversation"]
    id: RequestId
    params: ArchiveConversationParams


class ClientRequest_SendUserMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["sendUserMessage"]
    id: RequestId
    params: SendUserMessageParams


class ClientRequest_SendUserTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["sendUserTurn"]
    id: RequestId
    params: SendUserTurnParams


class ClientRequest_InterruptConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["interruptConversation"]
    id: RequestId
    params: InterruptConversationParams


class ClientRequest_AddConversationListener(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["addConversationListener"]
    id: RequestId
    params: AddConversationListenerParams


class ClientRequest_RemoveConversationListener(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["removeConversationListener"]
    id: RequestId
    params: RemoveConversationListenerParams


class ClientRequest_GitDiffToRemote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["gitDiffToRemote"]
    id: RequestId
    params: GitDiffToRemoteParams


class ClientRequest_LoginChatGpt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["loginChatGpt"]
    id: RequestId


class ClientRequest_CancelLoginChatGpt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["cancelLoginChatGpt"]
    id: RequestId
    params: CancelLoginChatGptParams


class ClientRequest_LogoutChatGpt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["logoutChatGpt"]
    id: RequestId


class ClientRequest_GetAuthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["getAuthStatus"]
    id: RequestId
    params: GetAuthStatusParams


class ClientRequest_GetUserSavedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["getUserSavedConfig"]
    id: RequestId


class ClientRequest_GetUserAgent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["getUserAgent"]
    id: RequestId


class ClientRequest_ExecOneOffCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["execOneOffCommand"]
    id: RequestId
    params: ExecOneOffCommandParams


class ContentItem_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["input_text"]
    text: str


class ContentItem_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["input_image"]
    image_url: str


class ContentItem_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["output_text"]
    text: str


class ConversationHistoryResponseEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: ConversationId
    entries: list[ResponseItem]


class ConversationSummary_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    path: str
    preview: str
    timestamp: str | None = None


class CustomPrompt_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    path: str
    content: str


class EmbeddedResource_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: EmbeddedResourceResource
    type: str


class ErrorEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


class EventMsg_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant5(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant6(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant7(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant8(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant9(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant10(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant11(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant12(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant13(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant14(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant15(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant16(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant17(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant18(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant19(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant20(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant21(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant22(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant23(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant24(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant25(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant26(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant27(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant28(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant29(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant30(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant31(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant32(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class EventMsg_Variant33(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["shutdown_complete"]


class EventMsg_Variant34(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ExecApprovalRequestEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None


class ExecCommandApprovalParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: ConversationId
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None


class ExecCommandApprovalResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ReviewDecision


class ExecCommandBeginEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]


class ExecCommandEndEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str


class ExecCommandOutputDeltaEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    stream: ExecOutputStream
    chunk: str


class ExecOneOffCommandParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: list[str]
    timeoutMs: int | None = None
    cwd: str | None = None
    sandboxPolicy: SandboxPolicy | None = None


class FileChange_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    add: dict[str, Any]


class FileChange_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delete: dict[str, Any]


class FileChange_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    update: dict[str, Any]


class FunctionCallOutputPayload_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    success: bool | None = None


class GetAuthStatusParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    includeToken: bool | None = None
    refreshToken: bool | None = None


class GetAuthStatusResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authMethod: AuthMode | None = None
    preferredAuthMethod: AuthMode
    authToken: str | None = None


class GetHistoryEntryResponseEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: float
    log_id: int
    entry: HistoryEntry | None = None


class GetUserAgentResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    userAgent: str


class GetUserSavedConfigResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: UserSavedConfig


class GitDiffToRemoteParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cwd: str


class GitDiffToRemoteResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha: GitSha
    diff: str


class HistoryEntry_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str
    ts: int
    text: str


class ImageContent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: str
    mimeType: str
    type: str


class InitializeResult_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: ServerCapabilities
    protocolVersion: str
    serverInfo: McpServerInfo


class InputItem_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text"]
    data: dict[str, Any]


class InputItem_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["image"]
    data: dict[str, Any]


class InputItem_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["localImage"]
    data: dict[str, Any]


class InterruptConversationParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId


class InterruptConversationResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    abortReason: TurnAbortReason


class ListConversationsParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pageSize: float | None = None
    cursor: str | None = None


class ListConversationsResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ConversationSummary]
    nextCursor: str | None = None


class ListCustomPromptsResponseEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    custom_prompts: list[CustomPrompt]


class LocalShellAction_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class LocalShellExecAction_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: list[str]
    timeout_ms: int | None = None
    working_directory: str | None = None
    env: dict[str, str] | None = None
    user: str | None = None


class LoginChatGptCompleteNotification_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loginId: str
    success: bool
    error: str | None = None


class LoginChatGptResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loginId: str
    authUrl: str


class LogoutChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class McpInvocation_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str
    tool: str
    arguments: JsonValue | None = None


class McpListToolsResponseEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tools: dict[str, Tool]


class McpServerInfo_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    user_agent: str


class McpToolCallBeginEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    invocation: McpInvocation


class McpToolCallEndEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]


class NewConversationParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = None
    profile: str | None = None
    cwd: str | None = None
    approvalPolicy: AskForApproval | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, JsonValue] | None = None
    baseInstructions: str | None = None
    includePlanTool: bool | None = None
    includeApplyPatchTool: bool | None = None


class NewConversationResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    model: str
    rolloutPath: str


class ParsedCommand_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["read"]
    cmd: str
    name: str


class ParsedCommand_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["list_files"]
    cmd: str
    path: str | None = None


class ParsedCommand_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["search"]
    cmd: str
    query: str | None = None
    path: str | None = None


class ParsedCommand_Variant4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["unknown"]
    cmd: str


class PatchApplyBeginEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]


class PatchApplyEndEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    stdout: str
    stderr: str
    success: bool


class PlanItemArg_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: str
    status: StepStatus


class Profile_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = None
    modelProvider: str | None = None
    approvalPolicy: AskForApproval | None = None
    modelReasoningEffort: ReasoningEffort | None = None
    modelReasoningSummary: ReasoningSummary | None = None
    modelVerbosity: Verbosity | None = None
    chatgptBaseUrl: str | None = None


class ReasoningItemContent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["reasoning_text"]
    text: str


class ReasoningItemContent_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text"]
    text: str


class ReasoningItemReasoningSummary_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["summary_text"]
    text: str


class RemoveConversationListenerParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscriptionId: str


class RemoveConversationSubscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ResourceLink_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    uri: str


class ResponseItem_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["message"]
    id: str | None = None
    role: str
    content: list[ContentItem]


class ResponseItem_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["reasoning"]
    summary: list[ReasoningItemReasoningSummary]
    encrypted_content: str | None = None


class ResponseItem_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["local_shell_call"]
    id: str | None = None
    call_id: str | None = None
    status: LocalShellStatus
    action: LocalShellAction


class ResponseItem_Variant4(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["function_call"]
    id: str | None = None
    name: str
    arguments: str
    call_id: str


class ResponseItem_Variant5(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["function_call_output"]
    call_id: str
    output: FunctionCallOutputPayload


class ResponseItem_Variant6(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["custom_tool_call"]
    id: str | None = None
    call_id: str
    name: str
    input: str


class ResponseItem_Variant7(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["custom_tool_call_output"]
    call_id: str
    output: str


class ResponseItem_Variant8(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["web_search_call"]
    id: str | None = None
    action: WebSearchAction


class ResponseItem_Variant9(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["other"]


class ResumeConversationParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    overrides: NewConversationParams | None = None


class ResumeConversationResponse_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    model: str
    initialMessages: list[EventMsg] | None = None


class SandboxPolicy_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["danger-full-access"]


class SandboxPolicy_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["read-only"]


class SandboxPolicy_Variant3(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["workspace-write"]
    network_access: bool
    exclude_tmpdir_env_var: bool
    exclude_slash_tmp: bool


class SandboxSettings_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    writableRoots: list[str]
    networkAccess: bool | None = None
    excludeTmpdirEnvVar: bool | None = None
    excludeSlashTmp: bool | None = None


class SendUserMessageParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    items: list[InputItem]


class SendUserMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class SendUserTurnParams_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationId: ConversationId
    items: list[InputItem]
    cwd: str
    approvalPolicy: AskForApproval
    sandboxPolicy: SandboxPolicy
    model: str
    effort: ReasoningEffort
    summary: ReasoningSummary


class SendUserTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ServerCapabilities_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ServerCapabilitiesPrompts_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ServerCapabilitiesResources_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ServerCapabilitiesTools_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ServerNotification_AuthStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["authStatusChange"]
    params: AuthStatusChangeNotification


class ServerNotification_LoginChatGptComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["loginChatGptComplete"]
    params: LoginChatGptCompleteNotification


class ServerRequest_ApplyPatchApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["applyPatchApproval"]
    id: RequestId
    params: ApplyPatchApprovalParams


class ServerRequest_ExecCommandApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["execCommandApproval"]
    id: RequestId
    params: ExecCommandApprovalParams


class SessionConfiguredEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: list[EventMsg] | None = None
    rollout_path: str


class StreamErrorEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str


class TaskCompleteEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_agent_message: str | None = None


class TaskStartedEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_context_window: int | None = None


class TextContent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    type: str


class TextResourceContents_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    uri: str


class TokenCountEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    info: TokenUsageInfo | None = None


class TokenUsage_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int


class TokenUsageInfo_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_token_usage: TokenUsage
    last_token_usage: TokenUsage
    model_context_window: int | None = None


class Tool_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputSchema: ToolInputSchema
    name: str


class ToolAnnotations_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pass


class ToolInputSchema_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class ToolOutputSchema_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str


class Tools_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    webSearch: bool | None = None
    viewImage: bool | None = None


class TurnAbortedEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: TurnAbortReason


class TurnDiffEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unified_diff: str


class UpdatePlanArgs_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    explanation: str | None = None
    plan: list[PlanItemArg]


class UserMessageEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    kind: InputMessageKind | None = None


class UserSavedConfig_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approvalPolicy: AskForApproval | None = None
    sandboxMode: SandboxMode | None = None
    sandboxSettings: SandboxSettings | None = None
    model: str | None = None
    modelReasoningEffort: ReasoningEffort | None = None
    modelReasoningSummary: ReasoningSummary | None = None
    modelVerbosity: Verbosity | None = None
    tools: Tools | None = None
    profile: str | None = None
    profiles: dict[str, Profile]


class WebSearchAction_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["search"]
    query: str


class WebSearchAction_Variant2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["other"]


class WebSearchBeginEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str


class WebSearchEndEvent_Variant1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    query: str


AddConversationListenerParams = AddConversationListenerParams_Variant1
AddConversationSubscriptionResponse = AddConversationSubscriptionResponse_Variant1
AgentMessageDeltaEvent = AgentMessageDeltaEvent_Variant1
AgentMessageEvent = AgentMessageEvent_Variant1
AgentReasoningDeltaEvent = AgentReasoningDeltaEvent_Variant1
AgentReasoningEvent = AgentReasoningEvent_Variant1
AgentReasoningRawContentDeltaEvent = AgentReasoningRawContentDeltaEvent_Variant1
AgentReasoningRawContentEvent = AgentReasoningRawContentEvent_Variant1
Annotations = Annotations_Variant1
ApplyPatchApprovalParams = ApplyPatchApprovalParams_Variant1
ApplyPatchApprovalRequestEvent = ApplyPatchApprovalRequestEvent_Variant1
ApplyPatchApprovalResponse = ApplyPatchApprovalResponse_Variant1
ArchiveConversationParams = ArchiveConversationParams_Variant1
AudioContent = AudioContent_Variant1
AuthStatusChangeNotification = AuthStatusChangeNotification_Variant1
BackgroundEventEvent = BackgroundEventEvent_Variant1
BlobResourceContents = BlobResourceContents_Variant1
CallToolResult = CallToolResult_Variant1
CancelLoginChatGptParams = CancelLoginChatGptParams_Variant1
ClientRequest = (
    ClientRequest_NewConversation
    | ClientRequest_ListConversations
    | ClientRequest_ResumeConversation
    | ClientRequest_ArchiveConversation
    | ClientRequest_SendUserMessage
    | ClientRequest_SendUserTurn
    | ClientRequest_InterruptConversation
    | ClientRequest_AddConversationListener
    | ClientRequest_RemoveConversationListener
    | ClientRequest_GitDiffToRemote
    | ClientRequest_LoginChatGpt
    | ClientRequest_CancelLoginChatGpt
    | ClientRequest_LogoutChatGpt
    | ClientRequest_GetAuthStatus
    | ClientRequest_GetUserSavedConfig
    | ClientRequest_GetUserAgent
    | ClientRequest_ExecOneOffCommand
)
ContentItem = ContentItem_Variant1 | ContentItem_Variant2 | ContentItem_Variant3
ConversationHistoryResponseEvent = ConversationHistoryResponseEvent_Variant1
ConversationSummary = ConversationSummary_Variant1
CustomPrompt = CustomPrompt_Variant1
EmbeddedResource = EmbeddedResource_Variant1
ErrorEvent = ErrorEvent_Variant1
EventMsg = (
    EventMsg_Variant1
    | EventMsg_Variant2
    | EventMsg_Variant3
    | EventMsg_Variant4
    | EventMsg_Variant5
    | EventMsg_Variant6
    | EventMsg_Variant7
    | EventMsg_Variant8
    | EventMsg_Variant9
    | EventMsg_Variant10
    | EventMsg_Variant11
    | EventMsg_Variant12
    | EventMsg_Variant13
    | EventMsg_Variant14
    | EventMsg_Variant15
    | EventMsg_Variant16
    | EventMsg_Variant17
    | EventMsg_Variant18
    | EventMsg_Variant19
    | EventMsg_Variant20
    | EventMsg_Variant21
    | EventMsg_Variant22
    | EventMsg_Variant23
    | EventMsg_Variant24
    | EventMsg_Variant25
    | EventMsg_Variant26
    | EventMsg_Variant27
    | EventMsg_Variant28
    | EventMsg_Variant29
    | EventMsg_Variant30
    | EventMsg_Variant31
    | EventMsg_Variant32
    | EventMsg_Variant33
    | EventMsg_Variant34
)
ExecApprovalRequestEvent = ExecApprovalRequestEvent_Variant1
ExecCommandApprovalParams = ExecCommandApprovalParams_Variant1
ExecCommandApprovalResponse = ExecCommandApprovalResponse_Variant1
ExecCommandBeginEvent = ExecCommandBeginEvent_Variant1
ExecCommandEndEvent = ExecCommandEndEvent_Variant1
ExecCommandOutputDeltaEvent = ExecCommandOutputDeltaEvent_Variant1
ExecOneOffCommandParams = ExecOneOffCommandParams_Variant1
FileChange = FileChange_Variant1 | FileChange_Variant2 | FileChange_Variant3
FunctionCallOutputPayload = FunctionCallOutputPayload_Variant1
GetAuthStatusParams = GetAuthStatusParams_Variant1
GetAuthStatusResponse = GetAuthStatusResponse_Variant1
GetHistoryEntryResponseEvent = GetHistoryEntryResponseEvent_Variant1
GetUserAgentResponse = GetUserAgentResponse_Variant1
GetUserSavedConfigResponse = GetUserSavedConfigResponse_Variant1
GitDiffToRemoteParams = GitDiffToRemoteParams_Variant1
GitDiffToRemoteResponse = GitDiffToRemoteResponse_Variant1
HistoryEntry = HistoryEntry_Variant1
ImageContent = ImageContent_Variant1
InitializeResult = InitializeResult_Variant1
InputItem = InputItem_Variant1 | InputItem_Variant2 | InputItem_Variant3
InterruptConversationParams = InterruptConversationParams_Variant1
InterruptConversationResponse = InterruptConversationResponse_Variant1
ListConversationsParams = ListConversationsParams_Variant1
ListConversationsResponse = ListConversationsResponse_Variant1
ListCustomPromptsResponseEvent = ListCustomPromptsResponseEvent_Variant1
LocalShellAction = LocalShellAction_Variant1
LocalShellExecAction = LocalShellExecAction_Variant1
LoginChatGptCompleteNotification = LoginChatGptCompleteNotification_Variant1
LoginChatGptResponse = LoginChatGptResponse_Variant1
McpInvocation = McpInvocation_Variant1
McpListToolsResponseEvent = McpListToolsResponseEvent_Variant1
McpServerInfo = McpServerInfo_Variant1
McpToolCallBeginEvent = McpToolCallBeginEvent_Variant1
McpToolCallEndEvent = McpToolCallEndEvent_Variant1
NewConversationParams = NewConversationParams_Variant1
NewConversationResponse = NewConversationResponse_Variant1
ParsedCommand = (
    ParsedCommand_Variant1
    | ParsedCommand_Variant2
    | ParsedCommand_Variant3
    | ParsedCommand_Variant4
)
PatchApplyBeginEvent = PatchApplyBeginEvent_Variant1
PatchApplyEndEvent = PatchApplyEndEvent_Variant1
PlanItemArg = PlanItemArg_Variant1
Profile = Profile_Variant1
ReasoningItemContent = ReasoningItemContent_Variant1 | ReasoningItemContent_Variant2
ReasoningItemReasoningSummary = ReasoningItemReasoningSummary_Variant1
RemoveConversationListenerParams = RemoveConversationListenerParams_Variant1
ResourceLink = ResourceLink_Variant1
ResponseItem = (
    ResponseItem_Variant1
    | ResponseItem_Variant2
    | ResponseItem_Variant3
    | ResponseItem_Variant4
    | ResponseItem_Variant5
    | ResponseItem_Variant6
    | ResponseItem_Variant7
    | ResponseItem_Variant8
    | ResponseItem_Variant9
)
ResumeConversationParams = ResumeConversationParams_Variant1
ResumeConversationResponse = ResumeConversationResponse_Variant1
SandboxPolicy = SandboxPolicy_Variant1 | SandboxPolicy_Variant2 | SandboxPolicy_Variant3
SandboxSettings = SandboxSettings_Variant1
SendUserMessageParams = SendUserMessageParams_Variant1
SendUserTurnParams = SendUserTurnParams_Variant1
ServerCapabilities = ServerCapabilities_Variant1
ServerCapabilitiesPrompts = ServerCapabilitiesPrompts_Variant1
ServerCapabilitiesResources = ServerCapabilitiesResources_Variant1
ServerCapabilitiesTools = ServerCapabilitiesTools_Variant1
ServerNotification = ServerNotification_AuthStatusChange | ServerNotification_LoginChatGptComplete
ServerRequest = ServerRequest_ApplyPatchApproval | ServerRequest_ExecCommandApproval
SessionConfiguredEvent = SessionConfiguredEvent_Variant1
StreamErrorEvent = StreamErrorEvent_Variant1
TaskCompleteEvent = TaskCompleteEvent_Variant1
TaskStartedEvent = TaskStartedEvent_Variant1
TextContent = TextContent_Variant1
TextResourceContents = TextResourceContents_Variant1
TokenCountEvent = TokenCountEvent_Variant1
TokenUsage = TokenUsage_Variant1
TokenUsageInfo = TokenUsageInfo_Variant1
Tool = Tool_Variant1
ToolAnnotations = ToolAnnotations_Variant1
ToolInputSchema = ToolInputSchema_Variant1
ToolOutputSchema = ToolOutputSchema_Variant1
Tools = Tools_Variant1
TurnAbortedEvent = TurnAbortedEvent_Variant1
TurnDiffEvent = TurnDiffEvent_Variant1
UpdatePlanArgs = UpdatePlanArgs_Variant1
UserMessageEvent = UserMessageEvent_Variant1
UserSavedConfig = UserSavedConfig_Variant1
WebSearchAction = WebSearchAction_Variant1 | WebSearchAction_Variant2
WebSearchBeginEvent = WebSearchBeginEvent_Variant1
WebSearchEndEvent = WebSearchEndEvent_Variant1

AskForApproval = (
    Literal["never"] | Literal["on-failure"] | Literal["on-request"] | Literal["untrusted"]
)
AuthMode = Literal["apikey"] | Literal["chatgpt"]
ContentBlock = AudioContent | EmbeddedResource | ImageContent | ResourceLink | TextContent
ConversationId = str
EmbeddedResourceResource = BlobResourceContents | TextResourceContents
ExecOutputStream = Literal["stderr"] | Literal["stdout"]
GitSha = str
InputMessageKind = Literal["environment_context"] | Literal["plain"] | Literal["user_instructions"]
LocalShellStatus = Literal["completed"] | Literal["in_progress"] | Literal["incomplete"]
ReasoningEffort = Literal["high"] | Literal["low"] | Literal["medium"] | Literal["minimal"]
ReasoningSummary = Literal["auto"] | Literal["concise"] | Literal["detailed"] | Literal["none"]
RequestId = int | str
ReviewDecision = (
    Literal["abort"] | Literal["approved"] | Literal["approved_for_session"] | Literal["denied"]
)
Role = Literal["assistant"] | Literal["user"]
SandboxMode = Literal["danger-full-access"] | Literal["read-only"] | Literal["workspace-write"]
StepStatus = Literal["completed"] | Literal["in_progress"] | Literal["pending"]
TurnAbortReason = Literal["interrupted"] | Literal["replaced"]
Verbosity = Literal["high"] | Literal["low"] | Literal["medium"]
JsonValue = Any
