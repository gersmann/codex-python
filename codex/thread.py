"""Thread abstractions for the simple `Codex` client."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from codex._turn_options import with_model_output_schema
from codex.app_server.errors import AppServerTurnError
from codex.app_server.options import (
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnOptions,
)
from codex.errors import ThreadRunError
from codex.options import (
    CancelSignal,
    SupportsAborted,
    SupportsIsSet,
    ThreadResumeOptions,
    ThreadStartOptions,
    TurnOptions,
)
from codex.protocol import types as protocol

if TYPE_CHECKING:
    from codex.app_server import AppServerClient, AppServerThread, TurnStream

type _ClientFactory = Callable[..., AppServerClient]

_ModelT = TypeVar("_ModelT", bound=BaseModel)
type InputItem = (
    str
    | Mapping[str, Any]
    | protocol.UserInput
    | protocol.TextUserInput
    | protocol.ImageUserInput
    | protocol.LocalImageUserInput
    | protocol.SkillUserInput
    | protocol.MentionUserInput
)
type Input = InputItem | Sequence[InputItem]


class CodexTurnStream:
    """Iterate over app-server notifications and aggregate final run state."""

    def __init__(
        self,
        stream: TurnStream,
        *,
        thread_id: str,
        signal: CancelSignal | None = None,
    ) -> None:
        self._stream = stream
        self._thread_id = thread_id
        self._closed = False
        self._interrupt_requested = False
        self._watcher = _SignalWatcher(self, signal)

    def __iter__(self) -> CodexTurnStream:
        return self

    def __next__(self) -> BaseModel:
        notification: BaseModel = next(self._stream)
        if self.final_turn is not None:
            self._watcher.stop()
        return notification

    @property
    def turn_id(self) -> str:
        return self._stream.initial_turn.id

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def final_text(self) -> str:
        return self._stream.final_text

    @property
    def usage(self) -> protocol.ThreadTokenUsage | None:
        return self._stream.usage

    @property
    def items(self) -> list[protocol.ThreadItem]:
        return self._stream.items

    @property
    def text_deltas(self) -> tuple[str, ...]:
        return self._stream.text_deltas

    @property
    def final_turn(self) -> protocol.Turn | None:
        return self._stream.final_turn

    def wait(self) -> CodexTurnStream:
        try:
            self._stream.wait()
            self._stream.raise_for_terminal_status()
        except AppServerTurnError as exc:
            raise ThreadRunError(str(exc), turn=exc.turn) from exc
        finally:
            self._watcher.stop()
        return self

    def collect(self) -> CodexTurnStream:
        return self.wait()

    def final_json(self) -> object:
        return self._stream.final_json()

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        return self._stream.final_model(model_type)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._watcher.stop()
        self._stream.close()

    def _interrupt(self) -> None:
        if self._interrupt_requested or self.final_turn is not None:
            return
        self._interrupt_requested = True
        self._stream.interrupt()


class Thread:
    """A simple conversation thread for the `Codex` client."""

    def __init__(
        self,
        client_factory: _ClientFactory,
        *,
        start_options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
        resume_options: ThreadResumeOptions | AppServerThreadResumeOptions | None = None,
        thread_id: str | None = None,
        tools: Collection[Callable[..., object]] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._start_options = start_options
        self._resume_options = resume_options
        self._id = thread_id
        self._thread: AppServerThread | None = None
        self._tools = tools

    @property
    def id(self) -> str | None:
        if self._thread is None:
            return self._id
        return self._thread.id

    def run(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        signal: CancelSignal | None = None,
    ) -> CodexTurnStream:
        """Start a streamed turn on this thread.

        Raises:
            ThreadRunError: pre-run interruption via `signal`.
        """
        effective_turn_options = turn_options or TurnOptions()
        if _is_signal_aborted(signal):
            raise ThreadRunError("Turn aborted: interrupted")
        thread = self._ensure_thread()
        stream = thread.run(input, _to_app_server_turn_options(effective_turn_options))
        return CodexTurnStream(stream, thread_id=thread.id, signal=signal)

    def run_text(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        signal: CancelSignal | None = None,
    ) -> str:
        """Run a turn and return final assistant text.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
        """
        stream = self.run(input, turn_options, signal=signal)
        stream.wait()
        return stream.final_text

    def run_json(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        signal: CancelSignal | None = None,
    ) -> object:
        """Run a turn and parse the final assistant message as JSON.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
            ValueError: no final assistant message or invalid JSON payload.
        """
        stream = self.run(input, turn_options, signal=signal)
        stream.wait()
        return stream.final_json()

    def run_model(
        self,
        input: Input,
        model_type: type[_ModelT],
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        signal: CancelSignal | None = None,
    ) -> _ModelT:
        """Run a turn and validate final assistant output with `model_type`.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
            ValueError: no final assistant message is available.
            pydantic.ValidationError: final message does not match `model_type`.
        """
        stream = self.run(
            input,
            with_model_output_schema(
                None if turn_options is None else _to_app_server_turn_options(turn_options),
                model_type,
                owner="Thread.run_model()",
            ),
            signal=signal,
        )
        stream.wait()
        return stream.final_model(model_type)

    def _ensure_thread(self) -> AppServerThread:
        if self._thread is not None:
            return self._thread

        client = self._client_factory(require_experimental=self._tools is not None)
        if self._id is None:
            self._thread = client.start_thread(
                _to_app_server_start_options(self._start_options),
                tools=self._tools,
            )
        else:
            self._thread = client.resume_thread(
                self._id,
                _to_app_server_resume_options(self._resume_options),
            )
        self._id = self._thread.id
        return self._thread


def _is_signal_aborted(signal: CancelSignal | None) -> bool:
    if signal is None:
        return False
    if isinstance(signal, SupportsAborted):
        return signal.aborted
    if isinstance(signal, SupportsIsSet):
        return bool(signal.is_set())
    raise TypeError("signal must expose `aborted` or `is_set()`")


def _to_app_server_start_options(
    options: ThreadStartOptions | AppServerThreadStartOptions | None,
) -> AppServerThreadStartOptions | None:
    if options is None:
        return None
    if isinstance(options, ThreadStartOptions):
        return options.to_app_server_options()
    return options


def _to_app_server_resume_options(
    options: ThreadResumeOptions | AppServerThreadResumeOptions | None,
) -> AppServerThreadResumeOptions | None:
    if options is None:
        return None
    if isinstance(options, ThreadResumeOptions):
        return options.to_app_server_options()
    return options


def _to_app_server_turn_options(
    options: TurnOptions | AppServerTurnOptions,
) -> AppServerTurnOptions:
    if isinstance(options, TurnOptions):
        return options.to_app_server_options()
    return options


class _SignalWatcher:
    def __init__(self, stream: CodexTurnStream, signal: CancelSignal | None) -> None:
        self._stream = stream
        self._signal = signal
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if signal is not None:
            self._thread = threading.Thread(target=self._run, name="codex-turn-signal", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=0.1)

    def _run(self) -> None:
        while not self._stop.is_set():
            if _is_signal_aborted(self._signal):
                try:
                    self._stream._interrupt()
                finally:
                    self._stop.set()
                return
            time.sleep(0.05)
