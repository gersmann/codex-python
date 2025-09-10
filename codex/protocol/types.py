# GENERATED CODE! DO NOT MODIFY BY HAND!
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from pydantic.config import ConfigDict


class AddConversationListenerParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId


class AddConversationSubscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subscriptionId: str


class AgentMessageDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delta: str


class AgentMessageEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str


class AgentReasoningDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delta: str


class AgentReasoningEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str


class AgentReasoningRawContentDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delta: str


class AgentReasoningRawContentEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str


class Annotations(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ApplyPatchApprovalParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: ConversationId
    call_id: str
    file_changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None


class ApplyPatchApprovalRequestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None


class ApplyPatchApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decision: ReviewDecision


class ArchiveConversationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    rolloutPath: str


class AudioContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: str
    mimeType: str
    type: str


class AuthStatusChangeNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    authMethod: AuthMode | None = None


class BackgroundEventEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str


class BlobResourceContents(BaseModel):
    model_config = ConfigDict(extra="ignore")
    blob: str
    uri: str


class CallToolResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: list[ContentBlock]


class CancelLoginChatGptParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    loginId: str


class ConversationHistoryResponseEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: ConversationId
    entries: list[ResponseItem]


class ConversationSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    path: str
    preview: str
    timestamp: str | None = None


class CustomPrompt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    path: str
    content: str


class EmbeddedResource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resource: EmbeddedResourceResource
    type: str


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str


class ExecApprovalRequestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None


class ExecCommandApprovalParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: ConversationId
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None


class ExecCommandApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decision: ReviewDecision


class ExecCommandBeginEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]


class ExecCommandEndEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str


class ExecCommandOutputDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    stream: ExecOutputStream
    chunk: str


class ExecOneOffCommandParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    command: list[str]
    timeoutMs: int | None = None
    cwd: str | None = None
    sandboxPolicy: SandboxPolicy | None = None


class FunctionCallOutputPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str
    success: bool | None = None


class GetAuthStatusParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    includeToken: bool | None = None
    refreshToken: bool | None = None


class GetAuthStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    authMethod: AuthMode | None = None
    preferredAuthMethod: AuthMode
    authToken: str | None = None


class GetHistoryEntryResponseEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    offset: float
    log_id: int
    entry: HistoryEntry | None = None


class GetUserAgentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    userAgent: str


class GetUserSavedConfigResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    config: UserSavedConfig


class GitDiffToRemoteParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cwd: str


class GitDiffToRemoteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sha: GitSha
    diff: str


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: str
    ts: int
    text: str


class ImageContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: str
    mimeType: str
    type: str


class InitializeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    capabilities: ServerCapabilities
    protocolVersion: str
    serverInfo: McpServerInfo


class InterruptConversationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId


class InterruptConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    abortReason: TurnAbortReason


class ListConversationsParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pageSize: float | None = None
    cursor: str | None = None


class ListConversationsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[ConversationSummary]
    nextCursor: str | None = None


class ListCustomPromptsResponseEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    custom_prompts: list[CustomPrompt]


class LocalShellAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class LocalShellExecAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    command: list[str]
    timeout_ms: int | None = None
    working_directory: str | None = None
    env: dict[str, str] | None = None
    user: str | None = None


class LoginChatGptCompleteNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    loginId: str
    success: bool
    error: str | None = None


class LoginChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    loginId: str
    authUrl: str


class McpInvocation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    server: str
    tool: str
    arguments: JsonValue | None = None


class McpListToolsResponseEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tools: dict[str, Tool]


class McpServerInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    version: str
    user_agent: str


class McpToolCallBeginEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    invocation: McpInvocation


class McpToolCallEndEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]


class NewConversationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str | None = None
    profile: str | None = None
    cwd: str | None = None
    approvalPolicy: AskForApproval | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, JsonValue] | None = None
    baseInstructions: str | None = None
    includePlanTool: bool | None = None
    includeApplyPatchTool: bool | None = None


class NewConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    model: str
    rolloutPath: str


class PatchApplyBeginEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]


class PatchApplyEndEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    stdout: str
    stderr: str
    success: bool


class PlanItemArg(BaseModel):
    model_config = ConfigDict(extra="ignore")
    step: str
    status: StepStatus


class Profile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str | None = None
    modelProvider: str | None = None
    approvalPolicy: AskForApproval | None = None
    modelReasoningEffort: ReasoningEffort | None = None
    modelReasoningSummary: ReasoningSummary | None = None
    modelVerbosity: Verbosity | None = None
    chatgptBaseUrl: str | None = None


class ReasoningItemReasoningSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["summary_text"]
    text: str


class RemoveConversationListenerParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subscriptionId: str


class ResourceLink(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: str
    uri: str


class ResumeConversationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    path: str
    overrides: NewConversationParams | None = None


class ResumeConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    model: str
    initialMessages: list[EventMsg] | None = None


class SandboxSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    writableRoots: list[str]
    networkAccess: bool | None = None
    excludeTmpdirEnvVar: bool | None = None
    excludeSlashTmp: bool | None = None


class SendUserMessageParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    items: list[InputItem]


class SendUserTurnParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversationId: ConversationId
    items: list[InputItem]
    cwd: str
    approvalPolicy: AskForApproval
    sandboxPolicy: SandboxPolicy
    model: str
    effort: ReasoningEffort
    summary: ReasoningSummary


class ServerCapabilities(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ServerCapabilitiesPrompts(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ServerCapabilitiesResources(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ServerCapabilitiesTools(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SessionConfiguredEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: list[EventMsg] | None = None
    rollout_path: str


class StreamErrorEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str


class TaskCompleteEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    last_agent_message: str | None = None


class TaskStartedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model_context_window: int | None = None


class TextContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    type: str


class TextResourceContents(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    uri: str


class TokenCountEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    info: TokenUsageInfo | None = None


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int


class TokenUsageInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_token_usage: TokenUsage
    last_token_usage: TokenUsage
    model_context_window: int | None = None


class Tool(BaseModel):
    model_config = ConfigDict(extra="ignore")
    inputSchema: ToolInputSchema
    name: str


class ToolAnnotations(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ToolInputSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str


class ToolOutputSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str


class Tools(BaseModel):
    model_config = ConfigDict(extra="ignore")
    webSearch: bool | None = None
    viewImage: bool | None = None


class TurnAbortedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reason: TurnAbortReason


class TurnDiffEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    unified_diff: str


class UpdatePlanArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    explanation: str | None = None
    plan: list[PlanItemArg]


class UserMessageEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str
    kind: InputMessageKind | None = None


class UserSavedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
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


class WebSearchBeginEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str


class WebSearchEndEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str
    query: str


class AskForApproval_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class AskForApproval_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class AskForApproval_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class AskForApproval_Variant4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class AuthMode_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class AuthMode_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ClientRequest_NewConversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["newConversation"]
    id: RequestId
    params: NewConversationParams


class ClientRequest_ListConversations(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["listConversations"]
    id: RequestId
    params: ListConversationsParams


class ClientRequest_ResumeConversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["resumeConversation"]
    id: RequestId
    params: ResumeConversationParams


class ClientRequest_ArchiveConversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["archiveConversation"]
    id: RequestId
    params: ArchiveConversationParams


class ClientRequest_SendUserMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["sendUserMessage"]
    id: RequestId
    params: SendUserMessageParams


class ClientRequest_SendUserTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["sendUserTurn"]
    id: RequestId
    params: SendUserTurnParams


class ClientRequest_InterruptConversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["interruptConversation"]
    id: RequestId
    params: InterruptConversationParams


class ClientRequest_AddConversationListener(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["addConversationListener"]
    id: RequestId
    params: AddConversationListenerParams


class ClientRequest_RemoveConversationListener(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["removeConversationListener"]
    id: RequestId
    params: RemoveConversationListenerParams


class ClientRequest_GitDiffToRemote(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["gitDiffToRemote"]
    id: RequestId
    params: GitDiffToRemoteParams


class ClientRequest_LoginChatGpt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["loginChatGpt"]
    id: RequestId


class ClientRequest_CancelLoginChatGpt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["cancelLoginChatGpt"]
    id: RequestId
    params: CancelLoginChatGptParams


class ClientRequest_LogoutChatGpt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["logoutChatGpt"]
    id: RequestId


class ClientRequest_GetAuthStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["getAuthStatus"]
    id: RequestId
    params: GetAuthStatusParams


class ClientRequest_GetUserSavedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["getUserSavedConfig"]
    id: RequestId


class ClientRequest_GetUserAgent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["getUserAgent"]
    id: RequestId


class ClientRequest_ExecOneOffCommand(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["execOneOffCommand"]
    id: RequestId
    params: ExecOneOffCommandParams


class ContentBlock_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    type: str


class ContentBlock_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: str
    mimeType: str
    type: str


class ContentBlock_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: str
    mimeType: str
    type: str


class ContentBlock_Variant4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: str
    uri: str


class ContentBlock_Variant5(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resource: EmbeddedResourceResource
    type: str


class ContentItem_InputText(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["input_text"]
    text: str


class ContentItem_InputImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["input_image"]
    image_url: str


class ContentItem_OutputText(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["output_text"]
    text: str


class EmbeddedResourceResource_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    uri: str


class EmbeddedResourceResource_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    blob: str
    uri: str


class EventMsg_Error(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["error"]
    message: str


class EventMsg_TaskStarted(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["task_started"]
    model_context_window: int | None = None


class EventMsg_TaskComplete(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["task_complete"]
    last_agent_message: str | None = None


class EventMsg_TokenCount(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["token_count"]
    info: TokenUsageInfo | None = None


class EventMsg_AgentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_message"]
    message: str


class EventMsg_UserMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["user_message"]
    message: str
    kind: InputMessageKind | None = None


class EventMsg_AgentMessageDelta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_message_delta"]
    delta: str


class EventMsg_AgentReasoning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_reasoning"]
    text: str


class EventMsg_AgentReasoningDelta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_reasoning_delta"]
    delta: str


class EventMsg_AgentReasoningRawContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_reasoning_raw_content"]
    text: str


class EventMsg_AgentReasoningRawContentDelta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_reasoning_raw_content_delta"]
    delta: str


class EventMsg_AgentReasoningSectionBreak(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["agent_reasoning_section_break"]


class EventMsg_SessionConfigured(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["session_configured"]
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: list[EventMsg] | None = None
    rollout_path: str


class EventMsg_McpToolCallBegin(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["mcp_tool_call_begin"]
    call_id: str
    invocation: McpInvocation


class EventMsg_McpToolCallEnd(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["mcp_tool_call_end"]
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]


class EventMsg_WebSearchBegin(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["web_search_begin"]
    call_id: str


class EventMsg_WebSearchEnd(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["web_search_end"]
    call_id: str
    query: str


class EventMsg_ExecCommandBegin(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["exec_command_begin"]
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]


class EventMsg_ExecCommandOutputDelta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["exec_command_output_delta"]
    call_id: str
    stream: ExecOutputStream
    chunk: str


class EventMsg_ExecCommandEnd(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["exec_command_end"]
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str


class EventMsg_ExecApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["exec_approval_request"]
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None


class EventMsg_ApplyPatchApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["apply_patch_approval_request"]
    call_id: str
    changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None


class EventMsg_BackgroundEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["background_event"]
    message: str


class EventMsg_StreamError(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["stream_error"]
    message: str


class EventMsg_PatchApplyBegin(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["patch_apply_begin"]
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]


class EventMsg_PatchApplyEnd(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["patch_apply_end"]
    call_id: str
    stdout: str
    stderr: str
    success: bool


class EventMsg_TurnDiff(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["turn_diff"]
    unified_diff: str


class EventMsg_GetHistoryEntryResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["get_history_entry_response"]
    offset: float
    log_id: int
    entry: HistoryEntry | None = None


class EventMsg_McpListToolsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["mcp_list_tools_response"]
    tools: dict[str, Tool]


class EventMsg_ListCustomPromptsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["list_custom_prompts_response"]
    custom_prompts: list[CustomPrompt]


class EventMsg_PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["plan_update"]
    explanation: str | None = None
    plan: list[PlanItemArg]


class EventMsg_TurnAborted(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["turn_aborted"]
    reason: TurnAbortReason


class EventMsg_ShutdownComplete(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["shutdown_complete"]


class EventMsg_ConversationHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["conversation_history"]
    conversation_id: ConversationId
    entries: list[ResponseItem]


class ExecOutputStream_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ExecOutputStream_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class FileChange_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    add: dict[str, Any]


class FileChange_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delete: dict[str, Any]


class FileChange_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update: dict[str, Any]


class InputItem_Text(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["text"]
    data: dict[str, Any]


class InputItem_Image(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["image"]
    data: dict[str, Any]


class InputItem_LocalImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["localImage"]
    data: dict[str, Any]


class InputMessageKind_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class InputMessageKind_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class InputMessageKind_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class LocalShellStatus_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class LocalShellStatus_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class LocalShellStatus_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ParsedCommand_Read(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["read"]
    cmd: str
    name: str


class ParsedCommand_ListFiles(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["list_files"]
    cmd: str
    path: str | None = None


class ParsedCommand_Search(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["search"]
    cmd: str
    query: str | None = None
    path: str | None = None


class ParsedCommand_Unknown(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["unknown"]
    cmd: str


class ReasoningEffort_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningEffort_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningEffort_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningEffort_Variant4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningItemContent_ReasoningText(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["reasoning_text"]
    text: str


class ReasoningItemContent_Text(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["text"]
    text: str


class ReasoningSummary_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningSummary_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningSummary_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReasoningSummary_Variant4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class RequestId_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class RequestId_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ResponseItem_Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["message"]
    id: str | None = None
    role: str
    content: list[ContentItem]


class ResponseItem_Reasoning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["reasoning"]
    summary: list[ReasoningItemReasoningSummary]
    encrypted_content: str | None = None


class ResponseItem_LocalShellCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["local_shell_call"]
    id: str | None = None
    call_id: str | None = None
    status: LocalShellStatus
    action: LocalShellAction


class ResponseItem_FunctionCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["function_call"]
    id: str | None = None
    name: str
    arguments: str
    call_id: str


class ResponseItem_FunctionCallOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["function_call_output"]
    call_id: str
    output: FunctionCallOutputPayload


class ResponseItem_CustomToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["custom_tool_call"]
    id: str | None = None
    call_id: str
    name: str
    input: str


class ResponseItem_CustomToolCallOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["custom_tool_call_output"]
    call_id: str
    output: str


class ResponseItem_WebSearchCall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["web_search_call"]
    id: str | None = None
    action: WebSearchAction


class ResponseItem_Other(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["other"]


class ReviewDecision_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReviewDecision_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReviewDecision_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ReviewDecision_Variant4(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class Role_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class Role_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SandboxMode_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SandboxMode_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SandboxMode_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SandboxPolicy_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mode: Literal["danger-full-access"]


class SandboxPolicy_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mode: Literal["read-only"]


class SandboxPolicy_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mode: Literal["workspace-write"]
    network_access: bool
    exclude_tmpdir_env_var: bool
    exclude_slash_tmp: bool


class ServerNotification_AuthStatusChange(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["authStatusChange"]
    params: AuthStatusChangeNotification


class ServerNotification_LoginChatGptComplete(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["loginChatGptComplete"]
    params: LoginChatGptCompleteNotification


class ServerRequest_ApplyPatchApproval(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["applyPatchApproval"]
    id: RequestId
    params: ApplyPatchApprovalParams


class ServerRequest_ExecCommandApproval(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Literal["execCommandApproval"]
    id: RequestId
    params: ExecCommandApprovalParams


class StepStatus_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class StepStatus_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class StepStatus_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class TurnAbortReason_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class TurnAbortReason_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class Verbosity_Variant1(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class Verbosity_Variant2(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class Verbosity_Variant3(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class WebSearchAction_Search(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["search"]
    query: str


class WebSearchAction_Other(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["other"]


class AgentReasoningSectionBreakEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class ArchiveConversationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class CancelLoginChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class LogoutChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class RemoveConversationSubscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SendUserMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


class SendUserTurnResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pass


AskForApproval = (
    AskForApproval_Variant1
    | AskForApproval_Variant2
    | AskForApproval_Variant3
    | AskForApproval_Variant4
)
AuthMode = AuthMode_Variant1 | AuthMode_Variant2
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
ContentBlock = (
    ContentBlock_Variant1
    | ContentBlock_Variant2
    | ContentBlock_Variant3
    | ContentBlock_Variant4
    | ContentBlock_Variant5
)
ContentItem = ContentItem_InputText | ContentItem_InputImage | ContentItem_OutputText
EmbeddedResourceResource = EmbeddedResourceResource_Variant1 | EmbeddedResourceResource_Variant2
EventMsg = (
    EventMsg_Error
    | EventMsg_TaskStarted
    | EventMsg_TaskComplete
    | EventMsg_TokenCount
    | EventMsg_AgentMessage
    | EventMsg_UserMessage
    | EventMsg_AgentMessageDelta
    | EventMsg_AgentReasoning
    | EventMsg_AgentReasoningDelta
    | EventMsg_AgentReasoningRawContent
    | EventMsg_AgentReasoningRawContentDelta
    | EventMsg_AgentReasoningSectionBreak
    | EventMsg_SessionConfigured
    | EventMsg_McpToolCallBegin
    | EventMsg_McpToolCallEnd
    | EventMsg_WebSearchBegin
    | EventMsg_WebSearchEnd
    | EventMsg_ExecCommandBegin
    | EventMsg_ExecCommandOutputDelta
    | EventMsg_ExecCommandEnd
    | EventMsg_ExecApprovalRequest
    | EventMsg_ApplyPatchApprovalRequest
    | EventMsg_BackgroundEvent
    | EventMsg_StreamError
    | EventMsg_PatchApplyBegin
    | EventMsg_PatchApplyEnd
    | EventMsg_TurnDiff
    | EventMsg_GetHistoryEntryResponse
    | EventMsg_McpListToolsResponse
    | EventMsg_ListCustomPromptsResponse
    | EventMsg_PlanUpdate
    | EventMsg_TurnAborted
    | EventMsg_ShutdownComplete
    | EventMsg_ConversationHistory
)
ExecOutputStream = ExecOutputStream_Variant1 | ExecOutputStream_Variant2
FileChange = FileChange_Variant1 | FileChange_Variant2 | FileChange_Variant3
InputItem = InputItem_Text | InputItem_Image | InputItem_LocalImage
InputMessageKind = InputMessageKind_Variant1 | InputMessageKind_Variant2 | InputMessageKind_Variant3
LocalShellStatus = LocalShellStatus_Variant1 | LocalShellStatus_Variant2 | LocalShellStatus_Variant3
ParsedCommand = (
    ParsedCommand_Read | ParsedCommand_ListFiles | ParsedCommand_Search | ParsedCommand_Unknown
)
ReasoningEffort = (
    ReasoningEffort_Variant1
    | ReasoningEffort_Variant2
    | ReasoningEffort_Variant3
    | ReasoningEffort_Variant4
)
ReasoningItemContent = ReasoningItemContent_ReasoningText | ReasoningItemContent_Text
ReasoningSummary = (
    ReasoningSummary_Variant1
    | ReasoningSummary_Variant2
    | ReasoningSummary_Variant3
    | ReasoningSummary_Variant4
)
RequestId = RequestId_Variant1 | RequestId_Variant2
ResponseItem = (
    ResponseItem_Message
    | ResponseItem_Reasoning
    | ResponseItem_LocalShellCall
    | ResponseItem_FunctionCall
    | ResponseItem_FunctionCallOutput
    | ResponseItem_CustomToolCall
    | ResponseItem_CustomToolCallOutput
    | ResponseItem_WebSearchCall
    | ResponseItem_Other
)
ReviewDecision = (
    ReviewDecision_Variant1
    | ReviewDecision_Variant2
    | ReviewDecision_Variant3
    | ReviewDecision_Variant4
)
Role = Role_Variant1 | Role_Variant2
SandboxMode = SandboxMode_Variant1 | SandboxMode_Variant2 | SandboxMode_Variant3
SandboxPolicy = SandboxPolicy_Variant1 | SandboxPolicy_Variant2 | SandboxPolicy_Variant3
ServerNotification = ServerNotification_AuthStatusChange | ServerNotification_LoginChatGptComplete
ServerRequest = ServerRequest_ApplyPatchApproval | ServerRequest_ExecCommandApproval
StepStatus = StepStatus_Variant1 | StepStatus_Variant2 | StepStatus_Variant3
TurnAbortReason = TurnAbortReason_Variant1 | TurnAbortReason_Variant2
Verbosity = Verbosity_Variant1 | Verbosity_Variant2 | Verbosity_Variant3
WebSearchAction = WebSearchAction_Search | WebSearchAction_Other

ConversationId = str
GitSha = str
JsonValue = Any
