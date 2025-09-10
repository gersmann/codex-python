# GENERATED CODE! DO NOT MODIFY BY HAND!
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from pydantic.config import ConfigDict


class AddConversationListenerParams(BaseModel):
    conversationId: ConversationId

    model_config = ConfigDict(extra="allow")


class AddConversationSubscriptionResponse(BaseModel):
    subscriptionId: str

    model_config = ConfigDict(extra="allow")


class AgentMessageDeltaEvent(BaseModel):
    delta: str

    model_config = ConfigDict(extra="allow")


class AgentMessageEvent(BaseModel):
    message: str

    model_config = ConfigDict(extra="allow")


class AgentReasoningDeltaEvent(BaseModel):
    delta: str

    model_config = ConfigDict(extra="allow")


class AgentReasoningEvent(BaseModel):
    text: str

    model_config = ConfigDict(extra="allow")


class AgentReasoningRawContentDeltaEvent(BaseModel):
    delta: str

    model_config = ConfigDict(extra="allow")


class AgentReasoningRawContentEvent(BaseModel):
    text: str

    model_config = ConfigDict(extra="allow")


class Annotations(BaseModel):
    model_config = ConfigDict(extra="allow")


class ApplyPatchApprovalParams(BaseModel):
    conversation_id: ConversationId
    call_id: str
    file_changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None

    model_config = ConfigDict(extra="allow")


class ApplyPatchApprovalRequestEvent(BaseModel):
    call_id: str
    changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None

    model_config = ConfigDict(extra="allow")


class ApplyPatchApprovalResponse(BaseModel):
    decision: ReviewDecision

    model_config = ConfigDict(extra="allow")


class ArchiveConversationParams(BaseModel):
    conversationId: ConversationId
    rolloutPath: str

    model_config = ConfigDict(extra="allow")


class AudioContent(BaseModel):
    data: str
    mimeType: str
    type: str

    model_config = ConfigDict(extra="allow")


class AuthStatusChangeNotification(BaseModel):
    authMethod: AuthMode | None = None

    model_config = ConfigDict(extra="allow")


class BackgroundEventEvent(BaseModel):
    message: str

    model_config = ConfigDict(extra="allow")


class BlobResourceContents(BaseModel):
    blob: str
    uri: str

    model_config = ConfigDict(extra="allow")


class CallToolResult(BaseModel):
    content: list[ContentBlock]

    model_config = ConfigDict(extra="allow")


class CancelLoginChatGptParams(BaseModel):
    loginId: str

    model_config = ConfigDict(extra="allow")


class ConversationHistoryResponseEvent(BaseModel):
    conversation_id: ConversationId
    entries: list[ResponseItem]

    model_config = ConfigDict(extra="allow")


class ConversationSummary(BaseModel):
    conversationId: ConversationId
    path: str
    preview: str
    timestamp: str | None = None

    model_config = ConfigDict(extra="allow")


class CustomPrompt(BaseModel):
    name: str
    path: str
    content: str

    model_config = ConfigDict(extra="allow")


class EmbeddedResource(BaseModel):
    resource: EmbeddedResourceResource
    type: str

    model_config = ConfigDict(extra="allow")


class ErrorEvent(BaseModel):
    message: str

    model_config = ConfigDict(extra="allow")


class ExecApprovalRequestEvent(BaseModel):
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None

    model_config = ConfigDict(extra="allow")


class ExecCommandApprovalParams(BaseModel):
    conversation_id: ConversationId
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None

    model_config = ConfigDict(extra="allow")


class ExecCommandApprovalResponse(BaseModel):
    decision: ReviewDecision

    model_config = ConfigDict(extra="allow")


class ExecCommandBeginEvent(BaseModel):
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]

    model_config = ConfigDict(extra="allow")


class ExecCommandEndEvent(BaseModel):
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str

    model_config = ConfigDict(extra="allow")


class ExecCommandOutputDeltaEvent(BaseModel):
    call_id: str
    stream: ExecOutputStream
    chunk: str

    model_config = ConfigDict(extra="allow")


class ExecOneOffCommandParams(BaseModel):
    command: list[str]
    timeoutMs: int | None = None
    cwd: str | None = None
    sandboxPolicy: SandboxPolicy | None = None

    model_config = ConfigDict(extra="allow")


class FunctionCallOutputPayload(BaseModel):
    content: str
    success: bool | None = None

    model_config = ConfigDict(extra="allow")


class GetAuthStatusParams(BaseModel):
    includeToken: bool | None = None
    refreshToken: bool | None = None

    model_config = ConfigDict(extra="allow")


class GetAuthStatusResponse(BaseModel):
    authMethod: AuthMode | None = None
    preferredAuthMethod: AuthMode
    authToken: str | None = None

    model_config = ConfigDict(extra="allow")


class GetHistoryEntryResponseEvent(BaseModel):
    offset: float
    log_id: int
    entry: HistoryEntry | None = None

    model_config = ConfigDict(extra="allow")


class GetUserAgentResponse(BaseModel):
    userAgent: str

    model_config = ConfigDict(extra="allow")


class GetUserSavedConfigResponse(BaseModel):
    config: UserSavedConfig

    model_config = ConfigDict(extra="allow")


class GitDiffToRemoteParams(BaseModel):
    cwd: str

    model_config = ConfigDict(extra="allow")


class GitDiffToRemoteResponse(BaseModel):
    sha: GitSha
    diff: str

    model_config = ConfigDict(extra="allow")


class HistoryEntry(BaseModel):
    conversation_id: str
    ts: int
    text: str

    model_config = ConfigDict(extra="allow")


class ImageContent(BaseModel):
    data: str
    mimeType: str
    type: str

    model_config = ConfigDict(extra="allow")


class InitializeResult(BaseModel):
    capabilities: ServerCapabilities
    protocolVersion: str
    serverInfo: McpServerInfo

    model_config = ConfigDict(extra="allow")


class InterruptConversationParams(BaseModel):
    conversationId: ConversationId

    model_config = ConfigDict(extra="allow")


class InterruptConversationResponse(BaseModel):
    abortReason: TurnAbortReason

    model_config = ConfigDict(extra="allow")


class ListConversationsParams(BaseModel):
    pageSize: float | None = None
    cursor: str | None = None

    model_config = ConfigDict(extra="allow")


class ListConversationsResponse(BaseModel):
    items: list[ConversationSummary]
    nextCursor: str | None = None

    model_config = ConfigDict(extra="allow")


class ListCustomPromptsResponseEvent(BaseModel):
    custom_prompts: list[CustomPrompt]

    model_config = ConfigDict(extra="allow")


class LocalShellAction(BaseModel):
    model_config = ConfigDict(extra="allow")


class LocalShellExecAction(BaseModel):
    command: list[str]
    timeout_ms: int | None = None
    working_directory: str | None = None
    env: dict[str, str] | None = None
    user: str | None = None

    model_config = ConfigDict(extra="allow")


class LoginChatGptCompleteNotification(BaseModel):
    loginId: str
    success: bool
    error: str | None = None

    model_config = ConfigDict(extra="allow")


class LoginChatGptResponse(BaseModel):
    loginId: str
    authUrl: str

    model_config = ConfigDict(extra="allow")


class McpInvocation(BaseModel):
    server: str
    tool: str
    arguments: JsonValue | None = None

    model_config = ConfigDict(extra="allow")


class McpListToolsResponseEvent(BaseModel):
    tools: dict[str, Tool]

    model_config = ConfigDict(extra="allow")


class McpServerInfo(BaseModel):
    name: str
    version: str
    user_agent: str

    model_config = ConfigDict(extra="allow")


class McpToolCallBeginEvent(BaseModel):
    call_id: str
    invocation: McpInvocation

    model_config = ConfigDict(extra="allow")


class McpToolCallEndEvent(BaseModel):
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class NewConversationParams(BaseModel):
    model: str | None = None
    profile: str | None = None
    cwd: str | None = None
    approvalPolicy: AskForApproval | None = None
    sandbox: SandboxMode | None = None
    config: dict[str, JsonValue] | None = None
    baseInstructions: str | None = None
    includePlanTool: bool | None = None
    includeApplyPatchTool: bool | None = None

    model_config = ConfigDict(extra="allow")


class NewConversationResponse(BaseModel):
    conversationId: ConversationId
    model: str
    rolloutPath: str

    model_config = ConfigDict(extra="allow")


class PatchApplyBeginEvent(BaseModel):
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]

    model_config = ConfigDict(extra="allow")


class PatchApplyEndEvent(BaseModel):
    call_id: str
    stdout: str
    stderr: str
    success: bool

    model_config = ConfigDict(extra="allow")


class PlanItemArg(BaseModel):
    step: str
    status: StepStatus

    model_config = ConfigDict(extra="allow")


class Profile(BaseModel):
    model: str | None = None
    modelProvider: str | None = None
    approvalPolicy: AskForApproval | None = None
    modelReasoningEffort: ReasoningEffort | None = None
    modelReasoningSummary: ReasoningSummary | None = None
    modelVerbosity: Verbosity | None = None
    chatgptBaseUrl: str | None = None

    model_config = ConfigDict(extra="allow")


class ReasoningItemReasoningSummary(BaseModel):
    type: Literal["summary_text"]
    text: str

    model_config = ConfigDict(extra="allow")


class RemoveConversationListenerParams(BaseModel):
    subscriptionId: str

    model_config = ConfigDict(extra="allow")


class ResourceLink(BaseModel):
    name: str
    type: str
    uri: str

    model_config = ConfigDict(extra="allow")


class ResumeConversationParams(BaseModel):
    path: str
    overrides: NewConversationParams | None = None

    model_config = ConfigDict(extra="allow")


class ResumeConversationResponse(BaseModel):
    conversationId: ConversationId
    model: str
    initialMessages: list[EventMsg] | None = None

    model_config = ConfigDict(extra="allow")


class SandboxSettings(BaseModel):
    writableRoots: list[str]
    networkAccess: bool | None = None
    excludeTmpdirEnvVar: bool | None = None
    excludeSlashTmp: bool | None = None

    model_config = ConfigDict(extra="allow")


class SendUserMessageParams(BaseModel):
    conversationId: ConversationId
    items: list[InputItem]

    model_config = ConfigDict(extra="allow")


class SendUserTurnParams(BaseModel):
    conversationId: ConversationId
    items: list[InputItem]
    cwd: str
    approvalPolicy: AskForApproval
    sandboxPolicy: SandboxPolicy
    model: str
    effort: ReasoningEffort
    summary: ReasoningSummary

    model_config = ConfigDict(extra="allow")


class ServerCapabilities(BaseModel):
    model_config = ConfigDict(extra="allow")


class ServerCapabilitiesPrompts(BaseModel):
    model_config = ConfigDict(extra="allow")


class ServerCapabilitiesResources(BaseModel):
    model_config = ConfigDict(extra="allow")


class ServerCapabilitiesTools(BaseModel):
    model_config = ConfigDict(extra="allow")


class SessionConfiguredEvent(BaseModel):
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: list[EventMsg] | None = None
    rollout_path: str

    model_config = ConfigDict(extra="allow")


class StreamErrorEvent(BaseModel):
    message: str

    model_config = ConfigDict(extra="allow")


class TaskCompleteEvent(BaseModel):
    last_agent_message: str | None = None

    model_config = ConfigDict(extra="allow")


class TaskStartedEvent(BaseModel):
    model_context_window: int | None = None

    model_config = ConfigDict(extra="allow")


class TextContent(BaseModel):
    text: str
    type: str

    model_config = ConfigDict(extra="allow")


class TextResourceContents(BaseModel):
    text: str
    uri: str

    model_config = ConfigDict(extra="allow")


class TokenCountEvent(BaseModel):
    info: TokenUsageInfo | None = None

    model_config = ConfigDict(extra="allow")


class TokenUsage(BaseModel):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int

    model_config = ConfigDict(extra="allow")


class TokenUsageInfo(BaseModel):
    total_token_usage: TokenUsage
    last_token_usage: TokenUsage
    model_context_window: int | None = None

    model_config = ConfigDict(extra="allow")


class Tool(BaseModel):
    inputSchema: ToolInputSchema
    name: str

    model_config = ConfigDict(extra="allow")


class ToolAnnotations(BaseModel):
    model_config = ConfigDict(extra="allow")


class ToolInputSchema(BaseModel):
    type: str

    model_config = ConfigDict(extra="allow")


class ToolOutputSchema(BaseModel):
    type: str

    model_config = ConfigDict(extra="allow")


class Tools(BaseModel):
    webSearch: bool | None = None
    viewImage: bool | None = None

    model_config = ConfigDict(extra="allow")


class TurnAbortedEvent(BaseModel):
    reason: TurnAbortReason

    model_config = ConfigDict(extra="allow")


class TurnDiffEvent(BaseModel):
    unified_diff: str

    model_config = ConfigDict(extra="allow")


class UpdatePlanArgs(BaseModel):
    explanation: str | None = None
    plan: list[PlanItemArg]

    model_config = ConfigDict(extra="allow")


class UserMessageEvent(BaseModel):
    message: str
    kind: InputMessageKind | None = None

    model_config = ConfigDict(extra="allow")


class UserSavedConfig(BaseModel):
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

    model_config = ConfigDict(extra="allow")


class WebSearchBeginEvent(BaseModel):
    call_id: str

    model_config = ConfigDict(extra="allow")


class WebSearchEndEvent(BaseModel):
    call_id: str
    query: str

    model_config = ConfigDict(extra="allow")


class AskForApproval_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class AskForApproval_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class AskForApproval_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class AskForApproval_Variant4(BaseModel):
    model_config = ConfigDict(extra="allow")


class AuthMode_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class AuthMode_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class ClientRequest_NewConversation(BaseModel):
    method: Literal["newConversation"]
    id: RequestId
    params: NewConversationParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_ListConversations(BaseModel):
    method: Literal["listConversations"]
    id: RequestId
    params: ListConversationsParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_ResumeConversation(BaseModel):
    method: Literal["resumeConversation"]
    id: RequestId
    params: ResumeConversationParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_ArchiveConversation(BaseModel):
    method: Literal["archiveConversation"]
    id: RequestId
    params: ArchiveConversationParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_SendUserMessage(BaseModel):
    method: Literal["sendUserMessage"]
    id: RequestId
    params: SendUserMessageParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_SendUserTurn(BaseModel):
    method: Literal["sendUserTurn"]
    id: RequestId
    params: SendUserTurnParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_InterruptConversation(BaseModel):
    method: Literal["interruptConversation"]
    id: RequestId
    params: InterruptConversationParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_AddConversationListener(BaseModel):
    method: Literal["addConversationListener"]
    id: RequestId
    params: AddConversationListenerParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_RemoveConversationListener(BaseModel):
    method: Literal["removeConversationListener"]
    id: RequestId
    params: RemoveConversationListenerParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_GitDiffToRemote(BaseModel):
    method: Literal["gitDiffToRemote"]
    id: RequestId
    params: GitDiffToRemoteParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_LoginChatGpt(BaseModel):
    method: Literal["loginChatGpt"]
    id: RequestId

    model_config = ConfigDict(extra="allow")


class ClientRequest_CancelLoginChatGpt(BaseModel):
    method: Literal["cancelLoginChatGpt"]
    id: RequestId
    params: CancelLoginChatGptParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_LogoutChatGpt(BaseModel):
    method: Literal["logoutChatGpt"]
    id: RequestId

    model_config = ConfigDict(extra="allow")


class ClientRequest_GetAuthStatus(BaseModel):
    method: Literal["getAuthStatus"]
    id: RequestId
    params: GetAuthStatusParams

    model_config = ConfigDict(extra="allow")


class ClientRequest_GetUserSavedConfig(BaseModel):
    method: Literal["getUserSavedConfig"]
    id: RequestId

    model_config = ConfigDict(extra="allow")


class ClientRequest_GetUserAgent(BaseModel):
    method: Literal["getUserAgent"]
    id: RequestId

    model_config = ConfigDict(extra="allow")


class ClientRequest_ExecOneOffCommand(BaseModel):
    method: Literal["execOneOffCommand"]
    id: RequestId
    params: ExecOneOffCommandParams

    model_config = ConfigDict(extra="allow")


class ContentBlock_Variant1(BaseModel):
    text: str
    type: str

    model_config = ConfigDict(extra="allow")


class ContentBlock_Variant2(BaseModel):
    data: str
    mimeType: str
    type: str

    model_config = ConfigDict(extra="allow")


class ContentBlock_Variant3(BaseModel):
    data: str
    mimeType: str
    type: str

    model_config = ConfigDict(extra="allow")


class ContentBlock_Variant4(BaseModel):
    name: str
    type: str
    uri: str

    model_config = ConfigDict(extra="allow")


class ContentBlock_Variant5(BaseModel):
    resource: EmbeddedResourceResource
    type: str

    model_config = ConfigDict(extra="allow")


class ContentItem_InputText(BaseModel):
    type: Literal["input_text"]
    text: str

    model_config = ConfigDict(extra="allow")


class ContentItem_InputImage(BaseModel):
    type: Literal["input_image"]
    image_url: str

    model_config = ConfigDict(extra="allow")


class ContentItem_OutputText(BaseModel):
    type: Literal["output_text"]
    text: str

    model_config = ConfigDict(extra="allow")


class EmbeddedResourceResource_Variant1(BaseModel):
    text: str
    uri: str

    model_config = ConfigDict(extra="allow")


class EmbeddedResourceResource_Variant2(BaseModel):
    blob: str
    uri: str

    model_config = ConfigDict(extra="allow")


class EventMsg_Error(BaseModel):
    type: Literal["error"]
    message: str

    model_config = ConfigDict(extra="allow")


class EventMsg_TaskStarted(BaseModel):
    type: Literal["task_started"]
    model_context_window: int | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_TaskComplete(BaseModel):
    type: Literal["task_complete"]
    last_agent_message: str | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_TokenCount(BaseModel):
    type: Literal["token_count"]
    info: TokenUsageInfo | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentMessage(BaseModel):
    type: Literal["agent_message"]
    message: str

    model_config = ConfigDict(extra="allow")


class EventMsg_UserMessage(BaseModel):
    type: Literal["user_message"]
    message: str
    kind: InputMessageKind | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentMessageDelta(BaseModel):
    type: Literal["agent_message_delta"]
    delta: str

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentReasoning(BaseModel):
    type: Literal["agent_reasoning"]
    text: str

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentReasoningDelta(BaseModel):
    type: Literal["agent_reasoning_delta"]
    delta: str

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentReasoningRawContent(BaseModel):
    type: Literal["agent_reasoning_raw_content"]
    text: str

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentReasoningRawContentDelta(BaseModel):
    type: Literal["agent_reasoning_raw_content_delta"]
    delta: str

    model_config = ConfigDict(extra="allow")


class EventMsg_AgentReasoningSectionBreak(BaseModel):
    type: Literal["agent_reasoning_section_break"]

    model_config = ConfigDict(extra="allow")


class EventMsg_SessionConfigured(BaseModel):
    type: Literal["session_configured"]
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: list[EventMsg] | None = None
    rollout_path: str

    model_config = ConfigDict(extra="allow")


class EventMsg_McpToolCallBegin(BaseModel):
    type: Literal["mcp_tool_call_begin"]
    call_id: str
    invocation: McpInvocation

    model_config = ConfigDict(extra="allow")


class EventMsg_McpToolCallEnd(BaseModel):
    type: Literal["mcp_tool_call_end"]
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class EventMsg_WebSearchBegin(BaseModel):
    type: Literal["web_search_begin"]
    call_id: str

    model_config = ConfigDict(extra="allow")


class EventMsg_WebSearchEnd(BaseModel):
    type: Literal["web_search_end"]
    call_id: str
    query: str

    model_config = ConfigDict(extra="allow")


class EventMsg_ExecCommandBegin(BaseModel):
    type: Literal["exec_command_begin"]
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]

    model_config = ConfigDict(extra="allow")


class EventMsg_ExecCommandOutputDelta(BaseModel):
    type: Literal["exec_command_output_delta"]
    call_id: str
    stream: ExecOutputStream
    chunk: str

    model_config = ConfigDict(extra="allow")


class EventMsg_ExecCommandEnd(BaseModel):
    type: Literal["exec_command_end"]
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str

    model_config = ConfigDict(extra="allow")


class EventMsg_ExecApprovalRequest(BaseModel):
    type: Literal["exec_approval_request"]
    call_id: str
    command: list[str]
    cwd: str
    reason: str | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_ApplyPatchApprovalRequest(BaseModel):
    type: Literal["apply_patch_approval_request"]
    call_id: str
    changes: dict[str, FileChange]
    reason: str | None = None
    grant_root: str | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_BackgroundEvent(BaseModel):
    type: Literal["background_event"]
    message: str

    model_config = ConfigDict(extra="allow")


class EventMsg_StreamError(BaseModel):
    type: Literal["stream_error"]
    message: str

    model_config = ConfigDict(extra="allow")


class EventMsg_PatchApplyBegin(BaseModel):
    type: Literal["patch_apply_begin"]
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]

    model_config = ConfigDict(extra="allow")


class EventMsg_PatchApplyEnd(BaseModel):
    type: Literal["patch_apply_end"]
    call_id: str
    stdout: str
    stderr: str
    success: bool

    model_config = ConfigDict(extra="allow")


class EventMsg_TurnDiff(BaseModel):
    type: Literal["turn_diff"]
    unified_diff: str

    model_config = ConfigDict(extra="allow")


class EventMsg_GetHistoryEntryResponse(BaseModel):
    type: Literal["get_history_entry_response"]
    offset: float
    log_id: int
    entry: HistoryEntry | None = None

    model_config = ConfigDict(extra="allow")


class EventMsg_McpListToolsResponse(BaseModel):
    type: Literal["mcp_list_tools_response"]
    tools: dict[str, Tool]

    model_config = ConfigDict(extra="allow")


class EventMsg_ListCustomPromptsResponse(BaseModel):
    type: Literal["list_custom_prompts_response"]
    custom_prompts: list[CustomPrompt]

    model_config = ConfigDict(extra="allow")


class EventMsg_PlanUpdate(BaseModel):
    type: Literal["plan_update"]
    explanation: str | None = None
    plan: list[PlanItemArg]

    model_config = ConfigDict(extra="allow")


class EventMsg_TurnAborted(BaseModel):
    type: Literal["turn_aborted"]
    reason: TurnAbortReason

    model_config = ConfigDict(extra="allow")


class EventMsg_ShutdownComplete(BaseModel):
    type: Literal["shutdown_complete"]

    model_config = ConfigDict(extra="allow")


class EventMsg_ConversationHistory(BaseModel):
    type: Literal["conversation_history"]
    conversation_id: ConversationId
    entries: list[ResponseItem]

    model_config = ConfigDict(extra="allow")


class ExecOutputStream_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExecOutputStream_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class FileChange_Variant1(BaseModel):
    add: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class FileChange_Variant2(BaseModel):
    delete: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class FileChange_Variant3(BaseModel):
    update: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class InputItem_Text(BaseModel):
    type: Literal["text"]
    data: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class InputItem_Image(BaseModel):
    type: Literal["image"]
    data: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class InputItem_LocalImage(BaseModel):
    type: Literal["localImage"]
    data: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class InputMessageKind_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class InputMessageKind_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class InputMessageKind_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class LocalShellStatus_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class LocalShellStatus_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class LocalShellStatus_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class ParsedCommand_Read(BaseModel):
    type: Literal["read"]
    cmd: str
    name: str

    model_config = ConfigDict(extra="allow")


class ParsedCommand_ListFiles(BaseModel):
    type: Literal["list_files"]
    cmd: str
    path: str | None = None

    model_config = ConfigDict(extra="allow")


class ParsedCommand_Search(BaseModel):
    type: Literal["search"]
    cmd: str
    query: str | None = None
    path: str | None = None

    model_config = ConfigDict(extra="allow")


class ParsedCommand_Unknown(BaseModel):
    type: Literal["unknown"]
    cmd: str

    model_config = ConfigDict(extra="allow")


class ReasoningEffort_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningEffort_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningEffort_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningEffort_Variant4(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningItemContent_ReasoningText(BaseModel):
    type: Literal["reasoning_text"]
    text: str

    model_config = ConfigDict(extra="allow")


class ReasoningItemContent_Text(BaseModel):
    type: Literal["text"]
    text: str

    model_config = ConfigDict(extra="allow")


class ReasoningSummary_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningSummary_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningSummary_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReasoningSummary_Variant4(BaseModel):
    model_config = ConfigDict(extra="allow")


class RequestId_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class RequestId_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class ResponseItem_Message(BaseModel):
    type: Literal["message"]
    id: str | None = None
    role: str
    content: list[ContentItem]

    model_config = ConfigDict(extra="allow")


class ResponseItem_Reasoning(BaseModel):
    type: Literal["reasoning"]
    summary: list[ReasoningItemReasoningSummary]
    encrypted_content: str | None = None

    model_config = ConfigDict(extra="allow")


class ResponseItem_LocalShellCall(BaseModel):
    type: Literal["local_shell_call"]
    id: str | None = None
    call_id: str | None = None
    status: LocalShellStatus
    action: LocalShellAction

    model_config = ConfigDict(extra="allow")


class ResponseItem_FunctionCall(BaseModel):
    type: Literal["function_call"]
    id: str | None = None
    name: str
    arguments: str
    call_id: str

    model_config = ConfigDict(extra="allow")


class ResponseItem_FunctionCallOutput(BaseModel):
    type: Literal["function_call_output"]
    call_id: str
    output: FunctionCallOutputPayload

    model_config = ConfigDict(extra="allow")


class ResponseItem_CustomToolCall(BaseModel):
    type: Literal["custom_tool_call"]
    id: str | None = None
    call_id: str
    name: str
    input: str

    model_config = ConfigDict(extra="allow")


class ResponseItem_CustomToolCallOutput(BaseModel):
    type: Literal["custom_tool_call_output"]
    call_id: str
    output: str

    model_config = ConfigDict(extra="allow")


class ResponseItem_WebSearchCall(BaseModel):
    type: Literal["web_search_call"]
    id: str | None = None
    action: WebSearchAction

    model_config = ConfigDict(extra="allow")


class ResponseItem_Other(BaseModel):
    type: Literal["other"]

    model_config = ConfigDict(extra="allow")


class ReviewDecision_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReviewDecision_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReviewDecision_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class ReviewDecision_Variant4(BaseModel):
    model_config = ConfigDict(extra="allow")


class Role_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class Role_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class SandboxMode_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class SandboxMode_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class SandboxMode_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class SandboxPolicy_Variant1(BaseModel):
    mode: Literal["danger-full-access"]

    model_config = ConfigDict(extra="allow")


class SandboxPolicy_Variant2(BaseModel):
    mode: Literal["read-only"]

    model_config = ConfigDict(extra="allow")


class SandboxPolicy_Variant3(BaseModel):
    mode: Literal["workspace-write"]
    network_access: bool
    exclude_tmpdir_env_var: bool
    exclude_slash_tmp: bool

    model_config = ConfigDict(extra="allow")


class ServerNotification_AuthStatusChange(BaseModel):
    method: Literal["authStatusChange"]
    params: AuthStatusChangeNotification

    model_config = ConfigDict(extra="allow")


class ServerNotification_LoginChatGptComplete(BaseModel):
    method: Literal["loginChatGptComplete"]
    params: LoginChatGptCompleteNotification

    model_config = ConfigDict(extra="allow")


class ServerRequest_ApplyPatchApproval(BaseModel):
    method: Literal["applyPatchApproval"]
    id: RequestId
    params: ApplyPatchApprovalParams

    model_config = ConfigDict(extra="allow")


class ServerRequest_ExecCommandApproval(BaseModel):
    method: Literal["execCommandApproval"]
    id: RequestId
    params: ExecCommandApprovalParams

    model_config = ConfigDict(extra="allow")


class StepStatus_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class StepStatus_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class StepStatus_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class TurnAbortReason_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class TurnAbortReason_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class Verbosity_Variant1(BaseModel):
    model_config = ConfigDict(extra="allow")


class Verbosity_Variant2(BaseModel):
    model_config = ConfigDict(extra="allow")


class Verbosity_Variant3(BaseModel):
    model_config = ConfigDict(extra="allow")


class WebSearchAction_Search(BaseModel):
    type: Literal["search"]
    query: str

    model_config = ConfigDict(extra="allow")


class WebSearchAction_Other(BaseModel):
    type: Literal["other"]

    model_config = ConfigDict(extra="allow")


class AgentReasoningSectionBreakEvent(BaseModel):
    model_config = ConfigDict(extra="allow")


class ArchiveConversationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class CancelLoginChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class LogoutChatGptResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class RemoveConversationSubscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class SendUserMessageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class SendUserTurnResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


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
