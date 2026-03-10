"""Thread abstractions for the exec-based Codex client."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from typing import Literal, Protocol, TypedDict, TypeVar, cast, get_args

from pydantic import BaseModel, ValidationError

from codex.errors import CodexParseError, ThreadRunError
from codex.exec import CodexExecArgs
from codex.options import CodexOptions, ThreadOptions, TurnOptions
from codex.output_schema_file import create_output_schema_file
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)


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
        self.items: list[protocol.TurnItem] = []
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
        if isinstance(event, protocol.SessionConfiguredEventMsg):
            self._thread._id = event.session_id.root
        elif isinstance(event, protocol.TaskStartedEventMsg):
            self.turn_id = event.turn_id
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
            item = event.item
            item_id = item.root.id
            if item_id in self._item_index:
                self.items[self._item_index[item_id]] = item
            else:
                self._item_index[item_id] = len(self.items)
                self.items.append(item)
            if isinstance(item.root, protocol.AgentMessageTurnItem):
                self.final_text = extract_agent_message_text(item.root)
                self._has_final_text = True
        elif isinstance(event, protocol.TaskCompleteEventMsg):
            if event.last_agent_message is not None:
                self.final_text = event.last_agent_message
                self._has_final_text = True
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
        stream = self.run(input, turn_options)
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
        raise CodexParseError(f"Unsupported exec event type: {event_type}")

    try:
        return event_model.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise CodexParseError(f"Failed to parse item: {raw_line}") from exc


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
