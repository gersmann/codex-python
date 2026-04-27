"""Async turn and thread orchestration for `codex app-server`."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar, cast

from pydantic import BaseModel

from codex._turn_options import with_model_output_schema
from codex.app_server._payloads import TurnInput, normalize_turn_input, serialize_value
from codex.app_server._protocol_helpers import (
    Notification,
    extract_item,
    extract_text_delta,
    extract_thread_id,
    extract_token_usage,
    extract_turn,
    extract_turn_id,
    method_name,
)
from codex.app_server._session import _AsyncNotificationSubscription
from codex.app_server.errors import AppServerTurnError
from codex.app_server.models import (
    EmptyResult,
    ReviewResult,
    ThreadResult,
    TurnIdResult,
    TurnResult,
)
from codex.app_server.options import AppServerThreadForkOptions, AppServerTurnOptions
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)
DEFAULT_REVIEW_DELIVERY = protocol.ReviewDelivery("inline")

_TURN_STREAM_NOTIFICATION_METHODS = {
    "turn/started",
    "turn/completed",
    "turn/diff/updated",
    "turn/plan/updated",
    "hook/started",
    "hook/completed",
    "thread/tokenUsage/updated",
    "item/started",
    "item/completed",
    "item/autoApprovalReview/started",
    "item/autoApprovalReview/completed",
    "item/agentMessage/delta",
    "item/plan/delta",
    "item/reasoning/summaryTextDelta",
    "item/reasoning/summaryPartAdded",
    "item/reasoning/textDelta",
    "item/commandExecution/outputDelta",
    "item/fileChange/outputDelta",
    "serverRequest/resolved",
}


class _TypedRpcClient(Protocol):
    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT: ...


class _NotificationSession(Protocol):
    def subscribe_notifications(
        self,
        methods: Collection[str] | None = None,
        *,
        predicate: Callable[[Notification], bool] | None = None,
    ) -> _AsyncNotificationSubscription: ...


class _ThreadClient(Protocol):
    rpc: _TypedRpcClient
    _session: _NotificationSession


@dataclass(slots=True)
class _StartedStream:
    subscription: _AsyncNotificationSubscription
    turn: protocol.Turn
    review_thread_id: str | None = None


class AsyncTurnStream:
    """Async iterator over protocol-native notifications for a single turn."""

    @staticmethod
    def _scope_predicate(
        thread_id: str,
        turn_id: str | None = None,
    ) -> Callable[[Notification], bool]:
        def predicate(notification: Notification) -> bool:
            if extract_thread_id(notification) != thread_id:
                return False
            if method_name(notification) == "thread/tokenUsage/updated":
                return True
            notification_turn_id = extract_turn_id(notification)
            return turn_id is None or notification_turn_id == turn_id

        return predicate

    @staticmethod
    def _reject_all_notifications(_: Notification) -> bool:
        return False

    def __init__(
        self,
        thread: AsyncAppServerThread,
        subscription: _AsyncNotificationSubscription,
        initial_turn: protocol.Turn,
        *,
        review_thread_id: str | None = None,
    ) -> None:
        self._thread = thread
        self._subscription = subscription
        self.initial_turn = initial_turn
        self.review_thread_id = review_thread_id
        self.turn_id = initial_turn.id
        self.thread_id = review_thread_id or thread.id
        self.final_turn: protocol.Turn | None = None
        self._final_text = ""
        self._final_message: protocol.AgentMessageThreadItem | None = None
        self.items: list[protocol.ThreadItem] = []
        self.usage: protocol.ThreadTokenUsage | None = None
        self._item_index: dict[str, int] = {}
        self._text_deltas: list[str] = []
        self._done = False
        self._closed = False

    @classmethod
    async def start(
        cls,
        thread: AsyncAppServerThread,
        params: BaseModel | Mapping[str, object],
    ) -> AsyncTurnStream:
        """Start a turn and return its notification stream."""
        result = await cls._bootstrap_stream(
            thread,
            method="turn/start",
            params=params,
            result_model=TurnResult,
            initial_predicate=cls._scope_predicate(thread.id),
            scope_from_result=lambda result: (thread.id, result.turn.id),
            review_thread_id_from_result=lambda result: None,
        )
        return cls(thread, result.subscription, result.turn)

    @classmethod
    async def start_review(
        cls,
        thread: AsyncAppServerThread,
        params: BaseModel | Mapping[str, object],
    ) -> AsyncTurnStream:
        """Start a review turn and return its notification stream."""
        result = await cls._bootstrap_stream(
            thread,
            method="review/start",
            params=params,
            result_model=ReviewResult,
            initial_predicate=cls._reject_all_notifications,
            scope_from_result=lambda result: (
                cast(ReviewResult, result).review_thread_id,
                result.turn.id,
            ),
            review_thread_id_from_result=lambda result: cast(ReviewResult, result).review_thread_id,
        )
        return cls(
            thread,
            result.subscription,
            result.turn,
            review_thread_id=result.review_thread_id,
        )

    def __aiter__(self) -> AsyncTurnStream:
        return self

    async def __anext__(self) -> Notification:
        if self._done:
            await self.close()
            raise StopAsyncIteration
        notification = await self._subscription.next()
        self._apply(notification)
        if isinstance(notification, protocol.TurnCompletedNotificationModel):
            self._done = True
        return notification

    async def wait(self) -> AsyncTurnStream:
        """Consume the stream to completion and return `self`."""
        try:
            if not self._done:
                async for _ in self:
                    pass
            self._require_terminal_turn()
        finally:
            await self.close()
        return self

    async def collect(self) -> AsyncTurnStream:
        """Alias for `wait()`."""
        return await self.wait()

    def raise_for_terminal_status(self) -> None:
        """Raise when the final turn completed unsuccessfully."""
        turn = self.final_turn
        if turn is None:
            raise ValueError(
                "No terminal turn is available yet. Wait for the turn stream to complete."
            )
        if turn.status.root == "failed":
            message = "Turn failed"
            if turn.error is not None:
                message = turn.error.message
            raise AppServerTurnError(message, turn=turn)
        if turn.status.root == "interrupted":
            raise AppServerTurnError("Turn aborted: interrupted", turn=turn)

    async def close(self) -> None:
        """Close the underlying notification subscription early."""
        if self._closed:
            return
        self._closed = True
        await self._subscription.close()

    @property
    def final_text(self) -> str:
        self._require_terminal_turn()
        return self._final_text

    @property
    def final_message(self) -> protocol.AgentMessageThreadItem | None:
        self._require_terminal_turn()
        return self._final_message

    async def steer(
        self,
        input: TurnInput,
        *,
        responsesapi_client_metadata: Mapping[str, object] | None = None,
    ) -> TurnIdResult:
        """Append additional user input to the in-flight turn."""
        payload: dict[str, object] = {
            "threadId": self.thread_id,
            "expectedTurnId": self.turn_id,
            "input": normalize_turn_input(input),
        }
        if responsesapi_client_metadata is not None:
            payload["responsesapiClientMetadata"] = dict(responsesapi_client_metadata)
        params = protocol.TurnSteerParams.model_validate(payload)
        return await self._thread._client.rpc.request_typed("turn/steer", params, TurnIdResult)

    async def interrupt(self) -> EmptyResult:
        """Interrupt the active turn."""
        params = protocol.TurnInterruptParams(threadId=self.thread_id, turnId=self.turn_id)
        return await self._thread._client.rpc.request_typed("turn/interrupt", params, EmptyResult)

    def final_json(self) -> object:
        """Parse the final assistant message text as JSON."""
        return json.loads(self._require_final_message_text())

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        """Validate the final assistant message text with a Pydantic model."""
        return model_type.model_validate_json(self._require_final_message_text())

    @property
    def text_deltas(self) -> tuple[str, ...]:
        """Return the streamed agent text deltas received so far."""
        return tuple(self._text_deltas)

    def _apply(self, notification: Notification) -> None:
        self._apply_text_delta(notification)
        self._apply_token_usage(notification)
        self._apply_item(notification)
        self._apply_turn_completion(notification)

    def _require_final_message_text(self) -> str:
        self._require_terminal_turn()
        if self._final_message is None:
            raise ValueError("No final message is available for the completed turn.")
        return self._final_message.text

    def _require_terminal_turn(self) -> protocol.Turn:
        if self.final_turn is None:
            raise ValueError(
                "No terminal turn is available yet. Wait for the turn stream to complete."
            )
        return self.final_turn

    def _apply_text_delta(self, notification: Notification) -> None:
        text_delta = extract_text_delta(notification)
        if text_delta is None:
            return
        self._text_deltas.append(text_delta)
        self._final_text += text_delta

    def _apply_token_usage(self, notification: Notification) -> None:
        token_usage = extract_token_usage(notification)
        if token_usage is not None:
            self.usage = token_usage

    def _apply_item(self, notification: Notification) -> None:
        item = extract_item(notification)
        if item is None:
            return
        item_id = getattr(item.root, "id", None)
        if isinstance(item_id, str) and item_id in self._item_index:
            self.items[self._item_index[item_id]] = item
        elif isinstance(item_id, str):
            self._item_index[item_id] = len(self.items)
            self.items.append(item)
        else:
            self.items.append(item)
        if isinstance(item.root, protocol.AgentMessageThreadItem):
            self._final_message = item.root
            self._final_text = item.root.text

    def _apply_turn_completion(self, notification: Notification) -> None:
        turn = extract_turn(notification)
        if turn is not None and isinstance(notification, protocol.TurnCompletedNotificationModel):
            self.final_turn = turn

    @classmethod
    async def _bootstrap_stream(
        cls,
        thread: AsyncAppServerThread,
        *,
        method: str,
        params: BaseModel | Mapping[str, object],
        result_model: type[TurnResult] | type[ReviewResult],
        initial_predicate: Callable[[Notification], bool],
        scope_from_result: Callable[[TurnResult | ReviewResult], tuple[str, str]],
        review_thread_id_from_result: Callable[[TurnResult | ReviewResult], str | None],
    ) -> _StartedStream:
        subscription = thread._client._session.subscribe_notifications(
            _TURN_STREAM_NOTIFICATION_METHODS,
            predicate=initial_predicate,
        )
        try:
            result: TurnResult | ReviewResult = await thread._client.rpc.request_typed(
                method,
                params,
                result_model,
            )
        except Exception:
            await subscription.close()
            raise
        scoped_thread_id, scoped_turn_id = scope_from_result(result)
        subscription.update_predicate(cls._scope_predicate(scoped_thread_id, scoped_turn_id))
        return _StartedStream(
            subscription=subscription,
            turn=result.turn,
            review_thread_id=review_thread_id_from_result(result),
        )


class AsyncAppServerThread:
    """Async OO wrapper around a single app-server thread."""

    def __init__(self, client: _ThreadClient, snapshot: protocol.Thread) -> None:
        self._client = client
        self._snapshot = snapshot

    @property
    def id(self) -> str:
        """Return the thread identifier."""
        return self.snapshot.id

    @property
    def snapshot(self) -> protocol.Thread:
        """Return the cached thread snapshot. Call `refresh()` after mutations for latest state."""
        return self._snapshot

    async def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
        """Reload the stored thread snapshot from app-server."""
        result = await self._client.rpc.request_typed(
            "thread/read",
            protocol.ThreadReadParams(threadId=self.id, includeTurns=include_turns),
            ThreadResult,
        )
        self._snapshot = result.thread
        return self.snapshot

    async def run(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> AsyncTurnStream:
        """Start a turn and return the protocol-native notification stream."""
        payload = (options or AppServerTurnOptions()).to_params(
            thread_id=self.id,
            input=normalize_turn_input(input),
        )
        return await AsyncTurnStream.start(self, payload)

    async def run_text(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> str:
        stream = await self.run(input, options)
        await stream.wait()
        stream.raise_for_terminal_status()
        return stream.final_text

    async def run_json(
        self,
        input: TurnInput,
        options: AppServerTurnOptions | None = None,
    ) -> object:
        stream = await self.run(input, options)
        await stream.wait()
        stream.raise_for_terminal_status()
        return stream.final_json()

    async def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        options: AppServerTurnOptions | None = None,
    ) -> _ModelT:
        """Run a turn and validate the final assistant text with `model_type`."""
        stream = await self.run(
            input,
            with_model_output_schema(
                options,
                model_type,
                owner="AppServerThread.run_model()",
            ),
        )
        await stream.wait()
        stream.raise_for_terminal_status()
        return stream.final_model(model_type)

    async def review(
        self,
        *,
        target: BaseModel,
        delivery: protocol.ReviewDelivery = DEFAULT_REVIEW_DELIVERY,
    ) -> AsyncTurnStream:
        """Start a review turn on this thread."""
        payload = protocol.ReviewStartParams.model_validate(
            {
                "threadId": self.id,
                "target": serialize_value(target),
                "delivery": delivery,
            }
        )
        return await AsyncTurnStream.start_review(self, payload)

    async def fork(
        self,
        options: AppServerThreadForkOptions | None = None,
    ) -> AsyncAppServerThread:
        """Fork this thread and return the new thread object."""
        payload = (options or AppServerThreadForkOptions()).to_params(thread_id=self.id)
        result = await self._client.rpc.request_typed("thread/fork", payload, ThreadResult)
        return AsyncAppServerThread(self._client, result.thread)

    async def archive(self) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/archive",
            protocol.ThreadArchiveParams(threadId=self.id),
            EmptyResult,
        )

    async def unarchive(self) -> protocol.Thread:
        """Restore an archived thread and update the cached snapshot from the response."""
        result = await self._client.rpc.request_typed(
            "thread/unarchive",
            protocol.ThreadUnarchiveParams(threadId=self.id),
            ThreadResult,
        )
        self._snapshot = result.thread
        return self.snapshot

    async def rollback(self, num_turns: int) -> protocol.Thread:
        """Roll back the last `num_turns` turns."""
        result = await self._client.rpc.request_typed(
            "thread/rollback",
            protocol.ThreadRollbackParams(threadId=self.id, numTurns=num_turns),
            ThreadResult,
        )
        self._snapshot = result.thread
        return self.snapshot

    async def compact(self) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/compact/start",
            protocol.ThreadCompactStartParams(threadId=self.id),
            EmptyResult,
        )

    async def set_name(self, name: str) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/name/set",
            protocol.ThreadSetNameParams(threadId=self.id, name=name),
            EmptyResult,
        )

    async def unsubscribe(self) -> EmptyResult:
        """Unsubscribe this connection from the loaded thread."""
        return await self._client.rpc.request_typed(
            "thread/unsubscribe",
            protocol.ThreadUnsubscribeParams(threadId=self.id),
            EmptyResult,
        )
