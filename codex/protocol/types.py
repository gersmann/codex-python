# GENERATED CODE! DO NOT MODIFY BY HAND!
from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class AddConversationListenerParams_Variant1(TypedDict):
    conversationId: ConversationId


class AddConversationSubscriptionResponse_Variant1(TypedDict):
    subscriptionId: str


class AgentMessageDeltaEvent_Variant1(TypedDict):
    delta: str


class AgentMessageEvent_Variant1(TypedDict):
    message: str


class AgentReasoningDeltaEvent_Variant1(TypedDict):
    delta: str


class AgentReasoningEvent_Variant1(TypedDict):
    text: str


class AgentReasoningRawContentDeltaEvent_Variant1(TypedDict):
    delta: str


class AgentReasoningRawContentEvent_Variant1(TypedDict):
    text: str


class AgentReasoningSectionBreakEvent(TypedDict):
    pass


class Annotations_Variant1(TypedDict):
    pass


class ApplyPatchApprovalParams_Variant1(TypedDict):
    conversation_id: ConversationId
    call_id: str
    file_changes: dict[str, FileChange]
    reason: NotRequired[str | None]
    grant_root: NotRequired[str | None]


class ApplyPatchApprovalRequestEvent_Variant1(TypedDict):
    call_id: str
    changes: dict[str, FileChange]
    reason: NotRequired[str | None]
    grant_root: NotRequired[str | None]


class ApplyPatchApprovalResponse_Variant1(TypedDict):
    decision: ReviewDecision


class ArchiveConversationParams_Variant1(TypedDict):
    conversationId: ConversationId
    rolloutPath: str


class ArchiveConversationResponse(TypedDict):
    pass


class AudioContent_Variant1(TypedDict):
    data: str
    mimeType: str
    type: str


class AuthStatusChangeNotification_Variant1(TypedDict):
    authMethod: NotRequired[AuthMode | None]


class BackgroundEventEvent_Variant1(TypedDict):
    message: str


class BlobResourceContents_Variant1(TypedDict):
    blob: str
    uri: str


class CallToolResult_Variant1(TypedDict):
    content: list[ContentBlock]


class CancelLoginChatGptParams_Variant1(TypedDict):
    loginId: str


class CancelLoginChatGptResponse(TypedDict):
    pass


class ClientRequest_NewConversation(TypedDict):
    method: Literal["newConversation"]
    id: RequestId
    params: NewConversationParams


class ClientRequest_ListConversations(TypedDict):
    method: Literal["listConversations"]
    id: RequestId
    params: ListConversationsParams


class ClientRequest_ResumeConversation(TypedDict):
    method: Literal["resumeConversation"]
    id: RequestId
    params: ResumeConversationParams


class ClientRequest_ArchiveConversation(TypedDict):
    method: Literal["archiveConversation"]
    id: RequestId
    params: ArchiveConversationParams


class ClientRequest_SendUserMessage(TypedDict):
    method: Literal["sendUserMessage"]
    id: RequestId
    params: SendUserMessageParams


class ClientRequest_SendUserTurn(TypedDict):
    method: Literal["sendUserTurn"]
    id: RequestId
    params: SendUserTurnParams


class ClientRequest_InterruptConversation(TypedDict):
    method: Literal["interruptConversation"]
    id: RequestId
    params: InterruptConversationParams


class ClientRequest_AddConversationListener(TypedDict):
    method: Literal["addConversationListener"]
    id: RequestId
    params: AddConversationListenerParams


class ClientRequest_RemoveConversationListener(TypedDict):
    method: Literal["removeConversationListener"]
    id: RequestId
    params: RemoveConversationListenerParams


class ClientRequest_GitDiffToRemote(TypedDict):
    method: Literal["gitDiffToRemote"]
    id: RequestId
    params: GitDiffToRemoteParams


class ClientRequest_LoginChatGpt(TypedDict):
    method: Literal["loginChatGpt"]
    id: RequestId


class ClientRequest_CancelLoginChatGpt(TypedDict):
    method: Literal["cancelLoginChatGpt"]
    id: RequestId
    params: CancelLoginChatGptParams


class ClientRequest_LogoutChatGpt(TypedDict):
    method: Literal["logoutChatGpt"]
    id: RequestId


class ClientRequest_GetAuthStatus(TypedDict):
    method: Literal["getAuthStatus"]
    id: RequestId
    params: GetAuthStatusParams


class ClientRequest_GetUserSavedConfig(TypedDict):
    method: Literal["getUserSavedConfig"]
    id: RequestId


class ClientRequest_GetUserAgent(TypedDict):
    method: Literal["getUserAgent"]
    id: RequestId


class ClientRequest_ExecOneOffCommand(TypedDict):
    method: Literal["execOneOffCommand"]
    id: RequestId
    params: ExecOneOffCommandParams


class ContentItem_Variant1(TypedDict):
    type: Literal["input_text"]
    text: str


class ContentItem_Variant2(TypedDict):
    type: Literal["input_image"]
    image_url: str


class ContentItem_Variant3(TypedDict):
    type: Literal["output_text"]
    text: str


class ConversationHistoryResponseEvent_Variant1(TypedDict):
    conversation_id: ConversationId
    entries: list[ResponseItem]


class ConversationSummary_Variant1(TypedDict):
    conversationId: ConversationId
    path: str
    preview: str
    timestamp: NotRequired[str | None]


class CustomPrompt_Variant1(TypedDict):
    name: str
    path: str
    content: str


class EmbeddedResource_Variant1(TypedDict):
    resource: EmbeddedResourceResource
    type: str


class ErrorEvent_Variant1(TypedDict):
    message: str


class EventMsg_Variant1(TypedDict):
    pass


class EventMsg_Variant2(TypedDict):
    pass


class EventMsg_Variant3(TypedDict):
    pass


class EventMsg_Variant4(TypedDict):
    pass


class EventMsg_Variant5(TypedDict):
    pass


class EventMsg_Variant6(TypedDict):
    pass


class EventMsg_Variant7(TypedDict):
    pass


class EventMsg_Variant8(TypedDict):
    pass


class EventMsg_Variant9(TypedDict):
    pass


class EventMsg_Variant10(TypedDict):
    pass


class EventMsg_Variant11(TypedDict):
    pass


class EventMsg_Variant12(TypedDict):
    pass


class EventMsg_Variant13(TypedDict):
    pass


class EventMsg_Variant14(TypedDict):
    pass


class EventMsg_Variant15(TypedDict):
    pass


class EventMsg_Variant16(TypedDict):
    pass


class EventMsg_Variant17(TypedDict):
    pass


class EventMsg_Variant18(TypedDict):
    pass


class EventMsg_Variant19(TypedDict):
    pass


class EventMsg_Variant20(TypedDict):
    pass


class EventMsg_Variant21(TypedDict):
    pass


class EventMsg_Variant22(TypedDict):
    pass


class EventMsg_Variant23(TypedDict):
    pass


class EventMsg_Variant24(TypedDict):
    pass


class EventMsg_Variant25(TypedDict):
    pass


class EventMsg_Variant26(TypedDict):
    pass


class EventMsg_Variant27(TypedDict):
    pass


class EventMsg_Variant28(TypedDict):
    pass


class EventMsg_Variant29(TypedDict):
    pass


class EventMsg_Variant30(TypedDict):
    pass


class EventMsg_Variant31(TypedDict):
    pass


class EventMsg_Variant32(TypedDict):
    pass


class EventMsg_Variant33(TypedDict):
    type: Literal["shutdown_complete"]


class EventMsg_Variant34(TypedDict):
    pass


class ExecApprovalRequestEvent_Variant1(TypedDict):
    call_id: str
    command: list[str]
    cwd: str
    reason: NotRequired[str | None]


class ExecCommandApprovalParams_Variant1(TypedDict):
    conversation_id: ConversationId
    call_id: str
    command: list[str]
    cwd: str
    reason: NotRequired[str | None]


class ExecCommandApprovalResponse_Variant1(TypedDict):
    decision: ReviewDecision


class ExecCommandBeginEvent_Variant1(TypedDict):
    call_id: str
    command: list[str]
    cwd: str
    parsed_cmd: list[ParsedCommand]


class ExecCommandEndEvent_Variant1(TypedDict):
    call_id: str
    stdout: str
    stderr: str
    aggregated_output: str
    exit_code: float
    duration: str
    formatted_output: str


class ExecCommandOutputDeltaEvent_Variant1(TypedDict):
    call_id: str
    stream: ExecOutputStream
    chunk: str


class ExecOneOffCommandParams_Variant1(TypedDict):
    command: list[str]
    timeoutMs: NotRequired[int | None]
    cwd: NotRequired[str | None]
    sandboxPolicy: NotRequired[SandboxPolicy | None]


class FileChange_Variant1(TypedDict):
    add: dict[str, Any]


class FileChange_Variant2(TypedDict):
    delete: dict[str, Any]


class FileChange_Variant3(TypedDict):
    update: dict[str, Any]


class FunctionCallOutputPayload_Variant1(TypedDict):
    content: str
    success: NotRequired[bool | None]


class GetAuthStatusParams_Variant1(TypedDict):
    includeToken: NotRequired[bool | None]
    refreshToken: NotRequired[bool | None]


class GetAuthStatusResponse_Variant1(TypedDict):
    authMethod: NotRequired[AuthMode | None]
    preferredAuthMethod: AuthMode
    authToken: NotRequired[str | None]


class GetHistoryEntryResponseEvent_Variant1(TypedDict):
    offset: float
    log_id: int
    entry: NotRequired[HistoryEntry | None]


class GetUserAgentResponse_Variant1(TypedDict):
    userAgent: str


class GetUserSavedConfigResponse_Variant1(TypedDict):
    config: UserSavedConfig


class GitDiffToRemoteParams_Variant1(TypedDict):
    cwd: str


class GitDiffToRemoteResponse_Variant1(TypedDict):
    sha: GitSha
    diff: str


class HistoryEntry_Variant1(TypedDict):
    conversation_id: str
    ts: int
    text: str


class ImageContent_Variant1(TypedDict):
    data: str
    mimeType: str
    type: str


class InitializeResult_Variant1(TypedDict):
    capabilities: ServerCapabilities
    protocolVersion: str
    serverInfo: McpServerInfo


class InputItem_Variant1(TypedDict):
    type: Literal["text"]
    data: dict[str, Any]


class InputItem_Variant2(TypedDict):
    type: Literal["image"]
    data: dict[str, Any]


class InputItem_Variant3(TypedDict):
    type: Literal["localImage"]
    data: dict[str, Any]


class InterruptConversationParams_Variant1(TypedDict):
    conversationId: ConversationId


class InterruptConversationResponse_Variant1(TypedDict):
    abortReason: TurnAbortReason


class ListConversationsParams_Variant1(TypedDict):
    pageSize: NotRequired[float | None]
    cursor: NotRequired[str | None]


class ListConversationsResponse_Variant1(TypedDict):
    items: list[ConversationSummary]
    nextCursor: NotRequired[str | None]


class ListCustomPromptsResponseEvent_Variant1(TypedDict):
    custom_prompts: list[CustomPrompt]


class LocalShellAction_Variant1(TypedDict):
    pass


class LocalShellExecAction_Variant1(TypedDict):
    command: list[str]
    timeout_ms: NotRequired[int | None]
    working_directory: NotRequired[str | None]
    env: NotRequired[dict[str, str] | None]
    user: NotRequired[str | None]


class LoginChatGptCompleteNotification_Variant1(TypedDict):
    loginId: str
    success: bool
    error: NotRequired[str | None]


class LoginChatGptResponse_Variant1(TypedDict):
    loginId: str
    authUrl: str


class LogoutChatGptResponse(TypedDict):
    pass


class McpInvocation_Variant1(TypedDict):
    server: str
    tool: str
    arguments: NotRequired[JsonValue | None]


class McpListToolsResponseEvent_Variant1(TypedDict):
    tools: dict[str, Tool]


class McpServerInfo_Variant1(TypedDict):
    name: str
    version: str
    user_agent: str


class McpToolCallBeginEvent_Variant1(TypedDict):
    call_id: str
    invocation: McpInvocation


class McpToolCallEndEvent_Variant1(TypedDict):
    call_id: str
    invocation: McpInvocation
    duration: str
    result: dict[str, Any]


class NewConversationParams_Variant1(TypedDict):
    model: NotRequired[str | None]
    profile: NotRequired[str | None]
    cwd: NotRequired[str | None]
    approvalPolicy: NotRequired[AskForApproval | None]
    sandbox: NotRequired[SandboxMode | None]
    config: NotRequired[dict[str, JsonValue] | None]
    baseInstructions: NotRequired[str | None]
    includePlanTool: NotRequired[bool | None]
    includeApplyPatchTool: NotRequired[bool | None]


class NewConversationResponse_Variant1(TypedDict):
    conversationId: ConversationId
    model: str
    rolloutPath: str


class ParsedCommand_Variant1(TypedDict):
    type: Literal["read"]
    cmd: str
    name: str


class ParsedCommand_Variant2(TypedDict):
    type: Literal["list_files"]
    cmd: str
    path: NotRequired[str | None]


class ParsedCommand_Variant3(TypedDict):
    type: Literal["search"]
    cmd: str
    query: NotRequired[str | None]
    path: NotRequired[str | None]


class ParsedCommand_Variant4(TypedDict):
    type: Literal["unknown"]
    cmd: str


class PatchApplyBeginEvent_Variant1(TypedDict):
    call_id: str
    auto_approved: bool
    changes: dict[str, FileChange]


class PatchApplyEndEvent_Variant1(TypedDict):
    call_id: str
    stdout: str
    stderr: str
    success: bool


class PlanItemArg_Variant1(TypedDict):
    step: str
    status: StepStatus


class Profile_Variant1(TypedDict):
    model: NotRequired[str | None]
    modelProvider: NotRequired[str | None]
    approvalPolicy: NotRequired[AskForApproval | None]
    modelReasoningEffort: NotRequired[ReasoningEffort | None]
    modelReasoningSummary: NotRequired[ReasoningSummary | None]
    modelVerbosity: NotRequired[Verbosity | None]
    chatgptBaseUrl: NotRequired[str | None]


class ReasoningItemContent_Variant1(TypedDict):
    type: Literal["reasoning_text"]
    text: str


class ReasoningItemContent_Variant2(TypedDict):
    type: Literal["text"]
    text: str


class ReasoningItemReasoningSummary_Variant1(TypedDict):
    type: Literal["summary_text"]
    text: str


class RemoveConversationListenerParams_Variant1(TypedDict):
    subscriptionId: str


class RemoveConversationSubscriptionResponse(TypedDict):
    pass


class ResourceLink_Variant1(TypedDict):
    name: str
    type: str
    uri: str


class ResponseItem_Variant1(TypedDict):
    type: Literal["message"]
    id: NotRequired[str | None]
    role: str
    content: list[ContentItem]


class ResponseItem_Variant2(TypedDict):
    type: Literal["reasoning"]
    summary: list[ReasoningItemReasoningSummary]
    encrypted_content: NotRequired[str | None]


class ResponseItem_Variant3(TypedDict):
    type: Literal["local_shell_call"]
    id: NotRequired[str | None]
    call_id: NotRequired[str | None]
    status: LocalShellStatus
    action: LocalShellAction


class ResponseItem_Variant4(TypedDict):
    type: Literal["function_call"]
    id: NotRequired[str | None]
    name: str
    arguments: str
    call_id: str


class ResponseItem_Variant5(TypedDict):
    type: Literal["function_call_output"]
    call_id: str
    output: FunctionCallOutputPayload


class ResponseItem_Variant6(TypedDict):
    type: Literal["custom_tool_call"]
    id: NotRequired[str | None]
    call_id: str
    name: str
    input: str


class ResponseItem_Variant7(TypedDict):
    type: Literal["custom_tool_call_output"]
    call_id: str
    output: str


class ResponseItem_Variant8(TypedDict):
    type: Literal["web_search_call"]
    id: NotRequired[str | None]
    action: WebSearchAction


class ResponseItem_Variant9(TypedDict):
    type: Literal["other"]


class ResumeConversationParams_Variant1(TypedDict):
    path: str
    overrides: NotRequired[NewConversationParams | None]


class ResumeConversationResponse_Variant1(TypedDict):
    conversationId: ConversationId
    model: str
    initialMessages: NotRequired[list[EventMsg] | None]


class SandboxPolicy_Variant1(TypedDict):
    mode: Literal["danger-full-access"]


class SandboxPolicy_Variant2(TypedDict):
    mode: Literal["read-only"]


class SandboxPolicy_Variant3(TypedDict):
    mode: Literal["workspace-write"]
    network_access: bool
    exclude_tmpdir_env_var: bool
    exclude_slash_tmp: bool


class SandboxSettings_Variant1(TypedDict):
    writableRoots: list[str]
    networkAccess: NotRequired[bool | None]
    excludeTmpdirEnvVar: NotRequired[bool | None]
    excludeSlashTmp: NotRequired[bool | None]


class SendUserMessageParams_Variant1(TypedDict):
    conversationId: ConversationId
    items: list[InputItem]


class SendUserMessageResponse(TypedDict):
    pass


class SendUserTurnParams_Variant1(TypedDict):
    conversationId: ConversationId
    items: list[InputItem]
    cwd: str
    approvalPolicy: AskForApproval
    sandboxPolicy: SandboxPolicy
    model: str
    effort: ReasoningEffort
    summary: ReasoningSummary


class SendUserTurnResponse(TypedDict):
    pass


class ServerCapabilities_Variant1(TypedDict):
    pass


class ServerCapabilitiesPrompts_Variant1(TypedDict):
    pass


class ServerCapabilitiesResources_Variant1(TypedDict):
    pass


class ServerCapabilitiesTools_Variant1(TypedDict):
    pass


class ServerNotification_AuthStatusChange(TypedDict):
    method: Literal["authStatusChange"]
    params: AuthStatusChangeNotification


class ServerNotification_LoginChatGptComplete(TypedDict):
    method: Literal["loginChatGptComplete"]
    params: LoginChatGptCompleteNotification


class ServerRequest_ApplyPatchApproval(TypedDict):
    method: Literal["applyPatchApproval"]
    id: RequestId
    params: ApplyPatchApprovalParams


class ServerRequest_ExecCommandApproval(TypedDict):
    method: Literal["execCommandApproval"]
    id: RequestId
    params: ExecCommandApprovalParams


class SessionConfiguredEvent_Variant1(TypedDict):
    session_id: ConversationId
    model: str
    history_log_id: int
    history_entry_count: float
    initial_messages: NotRequired[list[EventMsg] | None]
    rollout_path: str


class StreamErrorEvent_Variant1(TypedDict):
    message: str


class TaskCompleteEvent_Variant1(TypedDict):
    last_agent_message: NotRequired[str | None]


class TaskStartedEvent_Variant1(TypedDict):
    model_context_window: NotRequired[int | None]


class TextContent_Variant1(TypedDict):
    text: str
    type: str


class TextResourceContents_Variant1(TypedDict):
    text: str
    uri: str


class TokenCountEvent_Variant1(TypedDict):
    info: NotRequired[TokenUsageInfo | None]


class TokenUsage_Variant1(TypedDict):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int


class TokenUsageInfo_Variant1(TypedDict):
    total_token_usage: TokenUsage
    last_token_usage: TokenUsage
    model_context_window: NotRequired[int | None]


class Tool_Variant1(TypedDict):
    inputSchema: ToolInputSchema
    name: str


class ToolAnnotations_Variant1(TypedDict):
    pass


class ToolInputSchema_Variant1(TypedDict):
    type: str


class ToolOutputSchema_Variant1(TypedDict):
    type: str


class Tools_Variant1(TypedDict):
    webSearch: NotRequired[bool | None]
    viewImage: NotRequired[bool | None]


class TurnAbortedEvent_Variant1(TypedDict):
    reason: TurnAbortReason


class TurnDiffEvent_Variant1(TypedDict):
    unified_diff: str


class UpdatePlanArgs_Variant1(TypedDict):
    explanation: NotRequired[str | None]
    plan: list[PlanItemArg]


class UserMessageEvent_Variant1(TypedDict):
    message: str
    kind: NotRequired[InputMessageKind | None]


class UserSavedConfig_Variant1(TypedDict):
    approvalPolicy: NotRequired[AskForApproval | None]
    sandboxMode: NotRequired[SandboxMode | None]
    sandboxSettings: NotRequired[SandboxSettings | None]
    model: NotRequired[str | None]
    modelReasoningEffort: NotRequired[ReasoningEffort | None]
    modelReasoningSummary: NotRequired[ReasoningSummary | None]
    modelVerbosity: NotRequired[Verbosity | None]
    tools: NotRequired[Tools | None]
    profile: NotRequired[str | None]
    profiles: dict[str, Profile]


class WebSearchAction_Variant1(TypedDict):
    type: Literal["search"]
    query: str


class WebSearchAction_Variant2(TypedDict):
    type: Literal["other"]


class WebSearchBeginEvent_Variant1(TypedDict):
    call_id: str


class WebSearchEndEvent_Variant1(TypedDict):
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
