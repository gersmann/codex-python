from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from codex.app_server.errors import AppServerError
from codex.app_server.options import (
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnOptions,
)
from codex.errors import CodexError
from codex.options import (
    CancelSignal,
    CodexOptions,
    ThreadResumeOptions,
    ThreadStartOptions,
    TurnOptions,
)

if TYPE_CHECKING:
    from codex.app_server import AppServerClient
    from codex.thread import CodexTurnStream, Input, Thread

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class Codex:
    """Main entrypoint for interacting with Codex threads."""

    def __init__(self, options: CodexOptions | None = None) -> None:
        self._options = options or CodexOptions()
        self._client: AppServerClient | None = None
        self._closed = False

    def __enter__(self) -> Codex:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = (exc_type, exc, tb)
        self.close()

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    def start_thread(
        self,
        options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
    ) -> Thread:
        from codex.thread import Thread

        self._raise_if_closed()
        thread = Thread(self._ensure_client, start_options=options or ThreadStartOptions())
        thread._ensure_thread()
        return thread

    def resume_thread(
        self,
        thread_id: str,
        options: ThreadResumeOptions | AppServerThreadResumeOptions | None = None,
    ) -> Thread:
        from codex.thread import Thread

        self._raise_if_closed()
        if thread_id == "":
            raise ValueError("thread_id must be non-empty")
        thread = Thread(
            self._ensure_client,
            resume_options=options or ThreadResumeOptions(),
            thread_id=thread_id,
        )
        thread._ensure_thread()
        return thread

    def run(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        thread_options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
        signal: CancelSignal | None = None,
    ) -> CodexTurnStream:
        """Run a one-shot turn on a fresh internal thread.

        Raises:
            ThreadRunError: surfaced from stream consumption or `wait()`.
        """
        return self.start_thread(thread_options).run(input, turn_options, signal=signal)

    def run_text(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        thread_options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
        signal: CancelSignal | None = None,
    ) -> str:
        """Run a one-shot turn and return the final assistant text.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
        """
        return self.start_thread(thread_options).run_text(input, turn_options, signal=signal)

    def run_json(
        self,
        input: Input,
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        thread_options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
        signal: CancelSignal | None = None,
    ) -> object:
        """Run a one-shot turn and parse the final assistant message as JSON.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
            ValueError: no final assistant message or invalid JSON payload.
        """
        return self.start_thread(thread_options).run_json(input, turn_options, signal=signal)

    def run_model(
        self,
        input: Input,
        model_type: type[_ModelT],
        turn_options: TurnOptions | AppServerTurnOptions | None = None,
        *,
        thread_options: ThreadStartOptions | AppServerThreadStartOptions | None = None,
        signal: CancelSignal | None = None,
    ) -> _ModelT:
        """Run a one-shot turn and validate the final assistant message against `model_type`.

        Raises:
            ThreadRunError: terminal turn status is failed/interrupted.
            ValueError: no final assistant message is available.
            pydantic.ValidationError: final message does not match `model_type`.
        """
        return self.start_thread(thread_options).run_model(
            input,
            model_type,
            turn_options,
            signal=signal,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        client = self._client
        self._client = None
        if client is not None:
            client.close()

    def _ensure_client(self) -> AppServerClient:
        self._raise_if_closed()
        if self._client is None:
            from codex.app_server import AppServerClient

            client = AppServerClient.connect_stdio(
                process_options=self._options.to_app_server_options()
            )
            try:
                if self._options.api_key is not None:
                    client.account.login_api_key(api_key=self._options.api_key)
            except AppServerError:
                client.close()
                raise
            self._client = client
        return self._client

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise CodexError("Codex client is closed")
