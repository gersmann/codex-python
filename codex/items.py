from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

CommandExecutionStatus = Literal["in_progress", "completed", "failed"]
PatchChangeKind = Literal["add", "delete", "update"]
PatchApplyStatus = Literal["completed", "failed"]
McpToolCallStatus = Literal["in_progress", "completed", "failed"]


class CommandExecutionItem(TypedDict):
    id: str
    type: Literal["command_execution"]
    command: str
    aggregated_output: str
    status: CommandExecutionStatus
    exit_code: NotRequired[int]


class FileUpdateChange(TypedDict):
    path: str
    kind: PatchChangeKind


class FileChangeItem(TypedDict):
    id: str
    type: Literal["file_change"]
    changes: list[FileUpdateChange]
    status: PatchApplyStatus


class McpToolCallItem(TypedDict):
    id: str
    type: Literal["mcp_tool_call"]
    server: str
    tool: str
    status: McpToolCallStatus


class AgentMessageItem(TypedDict):
    id: str
    type: Literal["agent_message"]
    text: str


class ReasoningItem(TypedDict):
    id: str
    type: Literal["reasoning"]
    text: str


class WebSearchItem(TypedDict):
    id: str
    type: Literal["web_search"]
    query: str


class ErrorItem(TypedDict):
    id: str
    type: Literal["error"]
    message: str


class TodoItem(TypedDict):
    text: str
    completed: bool


class TodoListItem(TypedDict):
    id: str
    type: Literal["todo_list"]
    items: list[TodoItem]


ThreadItem = (
    AgentMessageItem
    | ReasoningItem
    | CommandExecutionItem
    | FileChangeItem
    | McpToolCallItem
    | WebSearchItem
    | TodoListItem
    | ErrorItem
)
