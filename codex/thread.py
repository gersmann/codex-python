from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict, cast

from codex.errors import CodexParseError, ThreadRunError
from codex.events import ThreadEvent, Usage
from codex.exec import CodexExecArgs
from codex.items import ThreadItem
from codex.options import CodexOptions, ThreadOptions, TurnOptions
from codex.output_schema_file import create_output_schema_file


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


@dataclass(slots=True, frozen=True)
class RunResult:
    items: list[ThreadItem]
    final_response: str
    usage: Usage | None


@dataclass(slots=True, frozen=True)
class RunStreamedResult:
    events: Iterator[ThreadEvent]


class Thread:
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
        return self._id

    def run_streamed(
        self, input: Input, turn_options: TurnOptions | None = None
    ) -> RunStreamedResult:
        return RunStreamedResult(events=self._run_streamed_internal(input, turn_options))

    def _run_streamed_internal(
        self, input: Input, turn_options: TurnOptions | None = None
    ) -> Iterator[ThreadEvent]:
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
            for item in self._exec.run(exec_args):
                parsed = parse_thread_event(item)
                if parsed["type"] == "thread.started":
                    self._id = parsed["thread_id"]
                yield parsed
        finally:
            schema_file.cleanup()

    def run(self, input: Input, turn_options: TurnOptions | None = None) -> RunResult:
        generator = self._run_streamed_internal(input, turn_options)
        items: list[ThreadItem] = []
        final_response = ""
        usage: Usage | None = None
        turn_failure: str | None = None
        for event in generator:
            event_dict = cast(dict[str, Any], event)
            event_type = event_dict.get("type")
            if event_type == "item.completed":
                item = event_dict.get("item")
                if isinstance(item, dict):
                    if item.get("type") == "agent_message":
                        text = item.get("text")
                        if isinstance(text, str):
                            final_response = text
                    items.append(cast(ThreadItem, item))
            elif event_type == "turn.completed":
                usage_value = event_dict.get("usage")
                if isinstance(usage_value, dict):
                    usage = cast(Usage, usage_value)
            elif event_type == "turn.failed":
                error_value = event_dict.get("error")
                if isinstance(error_value, dict):
                    message = error_value.get("message")
                    if isinstance(message, str):
                        turn_failure = message
                        break
        if turn_failure is not None:
            raise ThreadRunError(turn_failure)
        return RunResult(items=items, final_response=final_response, usage=usage)


def parse_thread_event(raw_line: str) -> ThreadEvent:
    try:
        parsed = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise CodexParseError(f"Failed to parse item: {raw_line}") from exc

    if not isinstance(parsed, Mapping):
        raise CodexParseError(f"Expected object event, received {type(parsed).__name__}")
    event_type = parsed.get("type")
    if not isinstance(event_type, str):
        raise CodexParseError("Event is missing string field 'type'")
    return cast(ThreadEvent, dict(parsed))


def normalize_input(input_value: Input) -> tuple[str, list[str]]:
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
