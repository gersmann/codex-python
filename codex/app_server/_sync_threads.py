"""Sync thread and stream wrappers for `codex app-server`."""

from __future__ import annotations

from collections.abc import Callable, Collection, Coroutine
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from codex.app_server._payloads import TurnInput
from codex.app_server._protocol_helpers import Notification
from codex.app_server._session import _AsyncNotificationSubscription
from codex.app_server._sync_support import _SyncRunner
from codex.app_server.models import EmptyResult, TurnIdResult
from codex.app_server.options import AppServerThreadForkOptions, AppServerTurnOptions
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)
DEFAULT_REVIEW_DELIVERY = protocol.ReviewDelivery("inline")


class _AsyncEventsClientLike(Protocol):
    def subscribe(
        self,
        methods: Collection[str] | None = None,
    ) -> _AsyncNotificationSubscription: ...


class _AsyncTurnStreamLike(Protocol):
    initial_turn: protocol.Turn
    final_turn: protocol.Turn | None
    final_text: str
    final_message: protocol.AgentMessageThreadItem | None
    items: list[protocol.ThreadItem]
    usage: protocol.ThreadTokenUsage | None
    text_deltas: tuple[str, ...]

    async def __anext__(self) -> Notification: ...

    async def wait(self) -> object: ...

    def final_json(self) -> object: ...

    def final_model(self, model_type: type[_ModelT]) -> _ModelT: ...

    def raise_for_terminal_status(self) -> None: ...

    async def steer(self, input: TurnInput) -> TurnIdResult: ...

    async def interrupt(self) -> EmptyResult: ...

    async def close(self) -> None: ...


class _AsyncThreadLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def snapshot(self) -> protocol.Thread: ...

    async def refresh(self, *, include_turns: bool = False) -> protocol.Thread: ...

    async def run(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> _AsyncTurnStreamLike: ...

    async def run_text(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> str: ...

    async def run_json(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> object: ...

    async def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        options: AppServerTurnOptions | None = None,
    ) -> _ModelT: ...

    async def review(
        self,
        *,
        target: BaseModel,
        delivery: protocol.ReviewDelivery = DEFAULT_REVIEW_DELIVERY,
    ) -> _AsyncTurnStreamLike: ...

    async def fork(self, options: AppServerThreadForkOptions | None = None) -> _AsyncThreadLike: ...

    async def archive(self) -> EmptyResult: ...

    async def unarchive(self) -> protocol.Thread: ...

    async def rollback(self, num_turns: int) -> protocol.Thread: ...

    async def compact(self) -> EmptyResult: ...

    async def set_name(self, name: str) -> EmptyResult: ...

    async def unsubscribe(self) -> EmptyResult: ...


class NotificationSubscription(_SyncRunner):
    """Synchronous iterator over connection-wide app-server notifications."""

    def __init__(
        self,
        async_subscription: _AsyncNotificationSubscription,
        run_awaitable: Callable[[Coroutine[Any, Any, object]], object],
    ) -> None:
        super().__init__(run_awaitable)
        self._async_subscription = async_subscription

    def __iter__(self) -> NotificationSubscription:
        return self

    def __next__(self) -> Notification:
        try:
            return self.next()
        except StopAsyncIteration as exc:
            raise StopIteration from exc

    def next(self) -> Notification:
        return self._run(self._async_subscription.next())

    def close(self) -> None:
        self._run(self._async_subscription.close())


class EventsClient(_SyncRunner):
    """Synchronous access to connection-wide app-server notifications."""

    def __init__(
        self,
        async_events: _AsyncEventsClientLike,
        run_awaitable: Callable[[Coroutine[Any, Any, object]], object],
    ) -> None:
        super().__init__(run_awaitable)
        self._async_events = async_events

    def subscribe(self, methods: Collection[str] | None = None) -> NotificationSubscription:
        return NotificationSubscription(
            self._async_events.subscribe(methods),
            self._run,
        )


class TurnStream(_SyncRunner):
    """Synchronous iterator over protocol-native notifications for a single turn."""

    def __init__(
        self,
        async_stream: _AsyncTurnStreamLike,
        run_awaitable: Callable[[Coroutine[Any, Any, object]], object],
    ) -> None:
        super().__init__(run_awaitable)
        self._async_stream = async_stream

    def __iter__(self) -> TurnStream:
        return self

    def __next__(self) -> Notification:
        try:
            return self._run(self._async_stream.__anext__())
        except StopAsyncIteration as exc:
            raise StopIteration from exc

    @property
    def initial_turn(self) -> protocol.Turn:
        return self._async_stream.initial_turn

    @property
    def final_turn(self) -> protocol.Turn | None:
        return self._async_stream.final_turn

    @property
    def final_text(self) -> str:
        return self._async_stream.final_text

    @property
    def final_message(self) -> protocol.AgentMessageThreadItem | None:
        return self._async_stream.final_message

    @property
    def items(self) -> list[protocol.ThreadItem]:
        return self._async_stream.items

    @property
    def usage(self) -> protocol.ThreadTokenUsage | None:
        return self._async_stream.usage

    @property
    def text_deltas(self) -> tuple[str, ...]:
        return self._async_stream.text_deltas

    def final_json(self) -> object:
        return self._async_stream.final_json()

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        return self._async_stream.final_model(model_type)

    def wait(self) -> TurnStream:
        self._run(self._async_stream.wait())
        return self

    def collect(self) -> TurnStream:
        return self.wait()

    def raise_for_terminal_status(self) -> None:
        self._async_stream.raise_for_terminal_status()

    def steer(self, input: TurnInput) -> TurnIdResult:
        return self._run(self._async_stream.steer(input))

    def interrupt(self) -> EmptyResult:
        return self._run(self._async_stream.interrupt())

    def close(self) -> None:
        self._run(self._async_stream.close())


class AppServerThread(_SyncRunner):
    """Synchronous OO wrapper around a single app-server thread."""

    def __init__(
        self,
        async_thread: _AsyncThreadLike,
        run_awaitable: Callable[[Coroutine[Any, Any, object]], object],
    ) -> None:
        super().__init__(run_awaitable)
        self._async_thread = async_thread

    @property
    def id(self) -> str:
        return self._async_thread.id

    @property
    def snapshot(self) -> protocol.Thread:
        return self._async_thread.snapshot

    def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
        return self._run(self._async_thread.refresh(include_turns=include_turns))

    def run(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> TurnStream:
        return TurnStream(
            self._run(self._async_thread.run(input, options)),
            self._run,
        )

    def run_text(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> str:
        return self._run(self._async_thread.run_text(input, options))

    def run_json(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> object:
        return self._run(self._async_thread.run_json(input, options))

    def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        options: AppServerTurnOptions | None = None,
    ) -> _ModelT:
        return self._run(self._async_thread.run_model(input, model_type, options))

    def review(
        self,
        *,
        target: BaseModel,
        delivery: protocol.ReviewDelivery = DEFAULT_REVIEW_DELIVERY,
    ) -> TurnStream:
        return TurnStream(
            self._run(
                self._async_thread.review(
                    target=target,
                    delivery=delivery,
                )
            ),
            self._run,
        )

    def fork(
        self,
        options: AppServerThreadForkOptions | None = None,
    ) -> AppServerThread:
        """Fork this thread and return the new thread object."""
        return AppServerThread(
            self._run(self._async_thread.fork(options)),
            self._run,
        )

    def archive(self) -> EmptyResult:
        return self._run(self._async_thread.archive())

    def unarchive(self) -> protocol.Thread:
        """Restore an archived thread and update the cached snapshot from the response."""
        return self._run(self._async_thread.unarchive())

    def rollback(self, num_turns: int) -> protocol.Thread:
        return self._run(self._async_thread.rollback(num_turns))

    def compact(self) -> EmptyResult:
        """Trigger thread compaction."""
        return self._run(self._async_thread.compact())

    def set_name(self, name: str) -> EmptyResult:
        return self._run(self._async_thread.set_name(name))

    def unsubscribe(self) -> EmptyResult:
        """Unsubscribe this connection from the loaded thread."""
        return self._run(self._async_thread.unsubscribe())
