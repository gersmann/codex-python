"""Thread abstractions for the exec-based Codex client."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Literal, Protocol, TypedDict, TypeVar, cast, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

from codex.errors import CodexParseError, ThreadRunError
from codex.exec import CodexExecArgs
from codex.options import CodexOptions, ThreadOptions, TurnOptions
from codex.output_schema import normalize_output_schema
from codex.output_schema_file import create_output_schema_file
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class _ExecAgentMessageItem(BaseModel):
    id: str
    type: Literal["agent_message"]
    text: str


class _ExecErrorItem(BaseModel):
    id: str
    type: Literal["error"]
    message: str


class _ExecCommandExecutionItem(BaseModel):
    id: str
    type: Literal["command_execution"]
    command: str
    aggregated_output: str | None = None
    exit_code: int | None = None
    status: str | None = None


class _ExecGenericItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str


class _ExecThreadStartedEvent(BaseModel):
    type: Literal["thread.started"]
    thread_id: str


class _ExecTurnStartedEvent(BaseModel):
    type: Literal["turn.started"]
    turn_id: str | None = None


class _ExecItemStartedEvent(BaseModel):
    type: Literal["item.started"]
    item: _ExecAgentMessageItem | _ExecErrorItem | _ExecCommandExecutionItem | _ExecGenericItem


class _ExecItemCompletedEvent(BaseModel):
    type: Literal["item.completed"]
    item: _ExecAgentMessageItem | _ExecErrorItem | _ExecCommandExecutionItem | _ExecGenericItem


class _ExecUsage(BaseModel):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int | None = None
    total_tokens: int | None = None

    def to_protocol(self) -> protocol.TokenUsage:
        reasoning_output_tokens = (
            0 if self.reasoning_output_tokens is None else self.reasoning_output_tokens
        )
        total_tokens = (
            self.input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + reasoning_output_tokens
            if self.total_tokens is None
            else self.total_tokens
        )
        return protocol.TokenUsage(
            input_tokens=self.input_tokens,
            cached_input_tokens=self.cached_input_tokens,
            output_tokens=self.output_tokens,
            reasoning_output_tokens=reasoning_output_tokens,
            total_tokens=total_tokens,
        )


class _ExecTurnCompletedEvent(BaseModel):
    type: Literal["turn.completed"]
    usage: _ExecUsage | None = None


class _ExecErrorPayload(BaseModel):
    message: str


class _ExecTurnFailedEvent(BaseModel):
    type: Literal["turn.failed"]
    error: _ExecErrorPayload


class _ExecErrorEvent(BaseModel):
    type: Literal["error"]
    message: str


class _ExecUnknownDottedEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str


type _ExecDottedItem = (
    _ExecAgentMessageItem | _ExecErrorItem | _ExecCommandExecutionItem | _ExecGenericItem
)
type _ExecStreamItem = protocol.TurnItem | _ExecDottedItem


def _build_exec_event_registry() -> dict[str, type[BaseModel]]:
    registry: dict[str, type[BaseModel]] = {}
    for candidate in vars(protocol).values():
        if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
            continue
        if candidate is protocol.EventMsg or not candidate.__name__.endswith("EventMsg"):
            continue
        type_field = candidate.model_fields.get("type")
        if type_field is None:
            continue
        type_annotation = type_field.annotation
        root_field = getattr(type_annotation, "model_fields", {}).get("root")
        if root_field is None:
            continue
        for literal_value in get_args(root_field.annotation):
            if isinstance(literal_value, str):
                registry[literal_value] = cast(type[BaseModel], candidate)
    return registry


EXEC_EVENT_TYPES = _build_exec_event_registry()


class ExecRunner(Protocol):
    def run(self, args: CodexExecArgs) -> Iterator[str]: ...


class TextInput(TypedDict):
    type: Literal["text"]
    text: str


class LocalImageInput(TypedDict):
    type: Literal["local_image"]
    path: str


UserInput = TextInput | LocalImageInput
Input = str | Sequence[UserInput]


class ExecTurnStream:
    """Iterate over typed exec events and aggregate final run state."""

    def __init__(self, events: Iterator[str], thread: Thread) -> None:
        self._events = events
        self._thread = thread
        self.turn_id: str | None = None
        self.final_text = ""
        self.usage: protocol.TokenUsage | None = None
        self.items: list[_ExecStreamItem] = []
        self._item_index: dict[str, int] = {}
        self._has_final_text = False
        self._text_deltas: list[str] = []
        self._error_message: str | None = None
        self._aborted_reason: str | None = None
        self._closed = False

    def __iter__(self) -> ExecTurnStream:
        return self

    def __next__(self) -> BaseModel:
        event = parse_exec_event(next(self._events))
        self._apply(event)
        return event

    @property
    def text_deltas(self) -> tuple[str, ...]:
        """Return the streamed assistant deltas received so far."""
        return tuple(self._text_deltas)

    def wait(self) -> ExecTurnStream:
        """Consume the stream to completion and return `self`."""
        try:
            for _ in self:
                pass
        finally:
            self.close()
        if self._error_message is not None:
            raise ThreadRunError(self._error_message)
        if self._aborted_reason is not None:
            raise ThreadRunError(f"Turn aborted: {self._aborted_reason}")
        return self

    def collect(self) -> ExecTurnStream:
        """Alias for `wait()`."""
        return self.wait()

    def final_json(self) -> object:
        """Parse the final assistant text as JSON."""
        return json.loads(self._require_final_text())

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        """Validate the final assistant text with a Pydantic model."""
        return model_type.model_validate_json(self._require_final_text())

    def close(self) -> None:
        """Close the underlying exec event iterator if it supports closing."""
        if self._closed:
            return
        self._closed = True
        close = getattr(self._events, "close", None)
        if callable(close):
            close()

    def _apply(self, event: BaseModel) -> None:
        if isinstance(event, _ExecThreadStartedEvent):
            self._thread._id = event.thread_id
        elif isinstance(event, protocol.SessionConfiguredEventMsg):
            self._thread._id = event.session_id.root
        elif isinstance(event, _ExecTurnStartedEvent):
            self.turn_id = event.turn_id
        elif isinstance(event, protocol.TaskStartedEventMsg):
            self.turn_id = event.turn_id
        elif isinstance(event, _ExecItemStartedEvent | _ExecItemCompletedEvent):
            item = event.item
            self._update_dotted_item(item)
            if isinstance(item, _ExecAgentMessageItem):
                self.final_text = item.text
                self._has_final_text = True
        elif isinstance(event, protocol.AgentMessageDeltaEventMsg):
            self._text_deltas.append(event.delta)
            self.final_text += event.delta
            self._has_final_text = True
        elif isinstance(event, protocol.AgentMessageEventMsg):
            self.final_text = event.message
            self._has_final_text = True
        elif isinstance(event, protocol.TokenCountEventMsg) and event.info is not None:
            self.usage = event.info.last_token_usage
        elif isinstance(event, protocol.ItemStartedEventMsg | protocol.ItemCompletedEventMsg):
            turn_item = event.item
            item_id = turn_item.root.id
            if item_id in self._item_index:
                self.items[self._item_index[item_id]] = turn_item
            else:
                self._item_index[item_id] = len(self.items)
                self.items.append(turn_item)
            if isinstance(turn_item.root, protocol.AgentMessageTurnItem):
                self.final_text = extract_agent_message_text(turn_item.root)
                self._has_final_text = True
        elif isinstance(event, _ExecTurnCompletedEvent):
            self.usage = None if event.usage is None else event.usage.to_protocol()
        elif isinstance(event, protocol.TaskCompleteEventMsg):
            if event.last_agent_message is not None:
                self.final_text = event.last_agent_message
                self._has_final_text = True
        elif isinstance(event, _ExecTurnFailedEvent):
            self._error_message = event.error.message
        elif isinstance(event, _ExecErrorEvent):
            self._error_message = event.message
        elif isinstance(event, protocol.ErrorEventMsg | protocol.StreamErrorEventMsg):
            self._error_message = event.message
        elif isinstance(event, protocol.TurnAbortedEventMsg):
            self._aborted_reason = event.reason.root

    def _require_final_text(self) -> str:
        if not self._has_final_text:
            raise ValueError(
                "No final text is available yet. Wait for the turn stream to complete."
            )
        return self.final_text

    def _update_dotted_item(self, item: _ExecDottedItem) -> None:
        item_id = item.id
        if item_id in self._item_index:
            self.items[self._item_index[item_id]] = item
        else:
            self._item_index[item_id] = len(self.items)
            self.items.append(item)


class Thread:
    """A CLI-backed conversation thread for the `Codex` client."""

    def __init__(
        self,
        exec_runner: ExecRunner,
        options: CodexOptions,
        thread_options: ThreadOptions,
        thread_id: str | None = None,
    ) -> None:
        self._exec = exec_runner
        self._options = options
        self._thread_options = thread_options
        self._id = thread_id

    @property
    def id(self) -> str | None:
        """Return the current thread id if the thread has been started."""
        return self._id

    def run(self, input: Input, turn_options: TurnOptions | None = None) -> ExecTurnStream:
        """Run a turn and return the typed exec event stream."""
        return ExecTurnStream(self._run_streamed_internal(input, turn_options), self)

    def run_text(self, input: Input, turn_options: TurnOptions | None = None) -> str:
        """Run a turn and return only the final assistant text."""
        stream = self.run(input, turn_options)
        stream.wait()
        return stream.final_text

    def run_json(self, input: Input, turn_options: TurnOptions | None = None) -> object:
        """Run a turn and parse the final assistant text as JSON."""
        stream = self.run(input, turn_options)
        stream.wait()
        return stream.final_json()

    def run_model(
        self,
        input: Input,
        model_type: type[_ModelT],
        turn_options: TurnOptions | None = None,
    ) -> _ModelT:
        """Run a turn and validate the final assistant text with `model_type`."""
        stream = self.run(input, _turn_options_with_model_schema(turn_options, model_type))
        stream.wait()
        return stream.final_model(model_type)

    def _run_streamed_internal(
        self, input: Input, turn_options: TurnOptions | None = None
    ) -> Iterator[str]:
        effective_turn_options = turn_options or TurnOptions()
        schema_file = create_output_schema_file(effective_turn_options.output_schema)
        prompt, images = normalize_input(input)
        options = self._thread_options
        exec_args = CodexExecArgs(
            input=prompt,
            base_url=self._options.base_url,
            api_key=self._options.api_key,
            thread_id=self._id,
            images=images,
            model=options.model,
            sandbox_mode=options.sandbox_mode,
            working_directory=options.working_directory,
            additional_directories=options.additional_directories,
            skip_git_repo_check=options.skip_git_repo_check,
            output_schema_file=schema_file.schema_path,
            model_reasoning_effort=options.model_reasoning_effort,
            signal=effective_turn_options.signal,
            network_access_enabled=options.network_access_enabled,
            web_search_mode=options.web_search_mode,
            web_search_enabled=options.web_search_enabled,
            approval_policy=options.approval_policy,
        )
        try:
            yield from self._exec.run(exec_args)
        finally:
            schema_file.cleanup()


def _turn_options_with_model_schema(
    turn_options: TurnOptions | None,
    model_type: type[BaseModel],
) -> TurnOptions:
    if turn_options is not None and normalize_output_schema(turn_options.output_schema) is not None:
        return turn_options
    signal = None if turn_options is None else turn_options.signal
    return TurnOptions(output_schema=model_type, signal=signal)


def parse_exec_event(raw_line: str) -> BaseModel:
    """Parse a single JSONL event line from `codex exec --experimental-json`."""
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise CodexParseError(f"Failed to parse item: {raw_line}") from exc

    if not isinstance(payload, dict):
        raise CodexParseError(f"Expected object event, received {type(payload).__name__}")

    event_type = payload.get("type")
    if not isinstance(event_type, str):
        raise CodexParseError("Event is missing string field 'type'")

    event_model = EXEC_EVENT_TYPES.get(event_type)
    if event_model is None:
        return _parse_dotted_exec_event(payload)

    try:
        return event_model.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise CodexParseError(f"Failed to parse item: {raw_line}") from exc


def _parse_dotted_exec_event(payload: dict[str, object]) -> BaseModel:
    event_type = payload["type"]
    if not isinstance(event_type, str):
        raise CodexParseError("Event is missing string field 'type'")
    try:
        if event_type == "thread.started":
            return _ExecThreadStartedEvent.model_validate(payload)
        if event_type == "turn.started":
            return _ExecTurnStartedEvent.model_validate(payload)
        if event_type == "item.started":
            item_payload = payload.get("item")
            return _ExecItemStartedEvent(
                type="item.started",
                item=_parse_dotted_exec_item(item_payload),
            )
        if event_type == "item.completed":
            item_payload = payload.get("item")
            return _ExecItemCompletedEvent(
                type="item.completed",
                item=_parse_dotted_exec_item(item_payload),
            )
        if event_type == "turn.completed":
            return _ExecTurnCompletedEvent.model_validate(payload)
        if event_type == "turn.failed":
            return _ExecTurnFailedEvent.model_validate(payload)
        if event_type == "error":
            return _ExecErrorEvent.model_validate(payload)
        if "." in event_type:
            return _ExecUnknownDottedEvent.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        raise CodexParseError(f"Failed to parse item: {json.dumps(payload)}") from exc
    raise CodexParseError(f"Unsupported exec event type: {event_type}")


def _parse_dotted_exec_item(payload: object) -> _ExecDottedItem:
    if not isinstance(payload, dict):
        raise ValueError("dotted exec item payload must be an object")
    item_type = payload.get("type")
    if item_type == "agent_message":
        return _ExecAgentMessageItem.model_validate(payload)
    if item_type == "error":
        return _ExecErrorItem.model_validate(payload)
    if item_type == "command_execution":
        return _ExecCommandExecutionItem.model_validate(payload)
    return _ExecGenericItem.model_validate(payload)


def extract_agent_message_text(item: protocol.AgentMessageTurnItem) -> str:
    """Extract plain text from an agent-message turn item."""
    return "".join(content.root.text for content in item.content)


def normalize_input(input_value: Input) -> tuple[str, list[str]]:
    """Normalize string or input-item lists into exec prompt and image arguments."""
    if isinstance(input_value, str):
        return input_value, []

    prompt_parts: list[str] = []
    images: list[str] = []
    for item in input_value:
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if not isinstance(text, str):
                raise ValueError("text input item requires string field 'text'")
            prompt_parts.append(text)
        elif item_type == "local_image":
            path = item.get("path")
            if not isinstance(path, str):
                raise ValueError("local_image input item requires string field 'path'")
            images.append(path)
        else:
            raise ValueError(f"Unsupported input item type: {item_type}")
    return "\n\n".join(prompt_parts), images
