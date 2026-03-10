"""Async public client surface for `codex app-server`."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import TypeVar

from pydantic import BaseModel

from codex.app_server._helpers import (
    Notification,
    RequestHandler,
    TurnInput,
    extract_item,
    extract_text_delta,
    extract_thread_id,
    extract_token_usage,
    extract_turn,
    extract_turn_id,
    merge_params,
    normalize_turn_input,
)
from codex.app_server._session import _AsyncNotificationSubscription, _AsyncSession
from codex.app_server.models import (
    EmptyResult,
    InitializeResult,
    LoadedThreadsResult,
    ReviewResult,
    ThreadListResult,
    ThreadResult,
    TurnIdResult,
    TurnResult,
)
from codex.app_server.options import AppServerInitializeOptions, AppServerProcessOptions
from codex.app_server.transports import (
    AsyncMessageTransport,
    AsyncStdioTransport,
    AsyncWebSocketTransport,
)
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class AsyncRpcClient:
    """Low-level async JSON-RPC access to app-server methods."""

    def __init__(self, session: _AsyncSession) -> None:
        self._session = session

    async def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        """Send a raw JSON-RPC request and return the decoded result."""
        return await self._session.request(method, params)

    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        """Send a request and validate the response with a Pydantic model."""
        return await self._session.request_typed(method, params, result_model)

    async def notify(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> None:
        """Send a JSON-RPC notification."""
        await self._session.notify(method, params)

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        """Register a handler for server-initiated JSON-RPC requests."""
        self._session.on_request(method, handler, request_model=request_model)


class AsyncServiceNamespace:
    """Helper for calling app-server methods with a shared prefix."""

    def __init__(self, rpc: AsyncRpcClient, prefix: str) -> None:
        self._rpc = rpc
        self._prefix = prefix

    async def call(
        self,
        suffix: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        """Call a method under the namespace prefix."""
        method = f"{self._prefix}/{suffix}" if suffix else self._prefix
        return await self._rpc.request(method, params)


class AsyncEventsClient:
    """Advanced subscription access to connection-wide notifications."""

    def __init__(self, session: _AsyncSession) -> None:
        self._session = session

    def subscribe(self, methods: Collection[str] | None = None) -> _AsyncNotificationSubscription:
        """Subscribe to raw notifications across the connection."""
        return self._session.subscribe_notifications(methods)


class AsyncTurnStream:
    """Async iterator over protocol-native notifications for a single turn."""

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
        self.final_text = ""
        self.final_message: protocol.AgentMessageThreadItem | None = None
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
        subscription = thread._client._session.subscribe_notifications()
        try:
            result = await thread._client.rpc.request_typed("turn/start", params, TurnResult)
        except Exception:
            await subscription.close()
            raise
        return cls(thread, subscription, result.turn)

    @classmethod
    async def start_review(
        cls,
        thread: AsyncAppServerThread,
        params: BaseModel | Mapping[str, object],
    ) -> AsyncTurnStream:
        """Start a review turn and return its notification stream."""
        subscription = thread._client._session.subscribe_notifications()
        try:
            result = await thread._client.rpc.request_typed("review/start", params, ReviewResult)
        except Exception:
            await subscription.close()
            raise
        return cls(thread, subscription, result.turn, review_thread_id=result.reviewThreadId)

    def __aiter__(self) -> AsyncTurnStream:
        return self

    async def __anext__(self) -> Notification:
        if self._done:
            await self.close()
            raise StopAsyncIteration
        while True:
            notification = await self._subscription.next()
            if not self._matches(notification):
                continue
            self._apply(notification)
            if isinstance(notification, protocol.TurnCompletedNotificationModel):
                self._done = True
            return notification

    async def wait(self) -> AsyncTurnStream:
        """Consume the stream to completion and return `self`."""
        if self._done:
            return self
        async for _ in self:
            pass
        return self

    async def collect(self) -> AsyncTurnStream:
        """Alias for `wait()`."""
        return await self.wait()

    async def close(self) -> None:
        """Close the underlying notification subscription early."""
        if self._closed:
            return
        self._closed = True
        await self._subscription.close()

    async def steer(self, input: TurnInput, **overrides: object) -> TurnIdResult:
        """Append additional user input to the in-flight turn."""
        params = merge_params(
            None,
            threadId=self.thread_id,
            expectedTurnId=self.turn_id,
            input=normalize_turn_input(input),
            **overrides,
        )
        return await self._thread._client.rpc.request_typed("turn/steer", params, TurnIdResult)

    async def interrupt(self) -> EmptyResult:
        """Interrupt the active turn."""
        params = merge_params(threadId=self.thread_id, turnId=self.turn_id)
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

    def _matches(self, notification: BaseModel) -> bool:
        thread_id = extract_thread_id(notification)
        if thread_id is not None and thread_id != self.thread_id:
            return False
        turn_id = extract_turn_id(notification)
        return turn_id is None or turn_id == self.turn_id

    def _apply(self, notification: Notification) -> None:
        text_delta = extract_text_delta(notification)
        if text_delta is not None:
            self._text_deltas.append(text_delta)
            self.final_text += text_delta
        token_usage = extract_token_usage(notification)
        if token_usage is not None:
            self.usage = token_usage
        item = extract_item(notification)
        if item is not None:
            item_id = getattr(item.root, "id", None)
            if isinstance(item_id, str) and item_id in self._item_index:
                self.items[self._item_index[item_id]] = item
            elif isinstance(item_id, str):
                self._item_index[item_id] = len(self.items)
                self.items.append(item)
            else:
                self.items.append(item)
            if isinstance(item.root, protocol.AgentMessageThreadItem):
                self.final_message = item.root
                self.final_text = item.root.text
        turn = extract_turn(notification)
        if turn is not None and isinstance(notification, protocol.TurnCompletedNotificationModel):
            self.final_turn = turn

    def _require_final_message_text(self) -> str:
        if self.final_message is None:
            raise ValueError(
                "No final message is available yet. Wait for the turn stream to complete."
            )
        return self.final_message.text


class AsyncAppServerThread:
    """Async OO wrapper around a single app-server thread."""

    def __init__(self, client: AsyncAppServerClient, snapshot: protocol.Thread) -> None:
        self._client = client
        self.snapshot = snapshot

    @property
    def id(self) -> str:
        """Return the thread identifier."""
        return self.snapshot.id

    async def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
        """Reload the stored thread snapshot from app-server."""
        result = await self._client.rpc.request_typed(
            "thread/read",
            merge_params(threadId=self.id, includeTurns=include_turns),
            ThreadResult,
        )
        self.snapshot = result.thread
        return self.snapshot

    async def run(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AsyncTurnStream:
        """Start a turn and return the protocol-native notification stream."""
        payload = merge_params(
            params,
            threadId=self.id,
            input=normalize_turn_input(input),
            **overrides,
        )
        return await AsyncTurnStream.start(self, payload)

    async def run_text(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> str:
        """Run a turn and return only the final assistant text."""
        stream = await self.run(input, params, **overrides)
        await stream.wait()
        return stream.final_text

    async def run_json(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> object:
        """Run a turn and parse the final assistant text as JSON."""
        stream = await self.run(input, params, **overrides)
        await stream.wait()
        return stream.final_json()

    async def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> _ModelT:
        """Run a turn and validate the final assistant text with `model_type`."""
        stream = await self.run(input, params, **overrides)
        await stream.wait()
        return stream.final_model(model_type)

    async def review(
        self,
        *,
        target: BaseModel | Mapping[str, object],
        delivery: str = "inline",
        params: Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AsyncTurnStream:
        """Start a review turn on this thread."""
        payload = merge_params(
            params,
            threadId=self.id,
            target=target,
            delivery=delivery,
            **overrides,
        )
        return await AsyncTurnStream.start_review(self, payload)

    async def fork(
        self, params: protocol.ThreadForkParams | Mapping[str, object] | None = None
    ) -> AsyncAppServerThread:
        """Fork this thread and return the new thread object."""
        payload = merge_params(params, threadId=self.id)
        result = await self._client.rpc.request_typed("thread/fork", payload, ThreadResult)
        return AsyncAppServerThread(self._client, result.thread)

    async def archive(self) -> EmptyResult:
        """Archive the thread."""
        return await self._client.rpc.request_typed(
            "thread/archive",
            merge_params(threadId=self.id),
            EmptyResult,
        )

    async def unarchive(self) -> protocol.Thread:
        """Restore an archived thread and refresh the local snapshot."""
        result = await self._client.rpc.request_typed(
            "thread/unarchive",
            merge_params(threadId=self.id),
            ThreadResult,
        )
        self.snapshot = result.thread
        return self.snapshot

    async def rollback(self, num_turns: int) -> protocol.Thread:
        """Roll back the last `num_turns` turns."""
        result = await self._client.rpc.request_typed(
            "thread/rollback",
            merge_params(threadId=self.id, numTurns=num_turns),
            ThreadResult,
        )
        self.snapshot = result.thread
        return self.snapshot

    async def compact(self) -> EmptyResult:
        """Trigger thread compaction."""
        return await self._client.rpc.request_typed(
            "thread/compact/start",
            merge_params(threadId=self.id),
            EmptyResult,
        )

    async def set_name(self, name: str) -> EmptyResult:
        """Set the user-facing thread name."""
        return await self._client.rpc.request_typed(
            "thread/name/set",
            merge_params(threadId=self.id, name=name),
            EmptyResult,
        )

    async def unsubscribe(self) -> object:
        """Unsubscribe this connection from the loaded thread."""
        return await self._client.rpc.request("thread/unsubscribe", merge_params(threadId=self.id))


class AsyncAppServerClient:
    """Async client for `codex app-server`."""

    def __init__(
        self,
        transport: AsyncMessageTransport,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> None:
        self._session = _AsyncSession(transport, initialize_options)
        self.rpc = AsyncRpcClient(self._session)
        self.events = AsyncEventsClient(self._session)
        self.models = AsyncServiceNamespace(self.rpc, "model")
        self.account = AsyncServiceNamespace(self.rpc, "account")
        self.config = AsyncServiceNamespace(self.rpc, "config")
        self.apps = AsyncServiceNamespace(self.rpc, "app")
        self.skills = AsyncServiceNamespace(self.rpc, "skills")
        self.mcp_servers = AsyncServiceNamespace(self.rpc, "mcpServer")
        self.feedback = AsyncServiceNamespace(self.rpc, "feedback")
        self.experimental_features = AsyncServiceNamespace(self.rpc, "experimentalFeature")
        self.collaboration_modes = AsyncServiceNamespace(self.rpc, "collaborationMode")
        self.windows_sandbox = AsyncServiceNamespace(self.rpc, "windowsSandbox")

    @classmethod
    async def connect_stdio(
        cls,
        process_options: AppServerProcessOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AsyncAppServerClient:
        """Start `codex app-server` over stdio and initialize the session."""
        client = cls(AsyncStdioTransport(process_options), initialize_options)
        await client.start()
        return client

    @classmethod
    async def connect_websocket(
        cls,
        url: str,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AsyncAppServerClient:
        """Connect to an app-server websocket endpoint and initialize the session."""
        client = cls(AsyncWebSocketTransport(url), initialize_options)
        await client.start()
        return client

    async def __aenter__(self) -> AsyncAppServerClient:
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = (exc_type, exc, tb)
        await self.close()

    async def start(self) -> InitializeResult:
        """Start the transport and complete the initialize handshake."""
        return await self._session.start()

    async def close(self) -> None:
        """Close the app-server session and transport."""
        await self._session.close()

    async def start_thread(
        self,
        params: protocol.ThreadStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AsyncAppServerThread:
        """Create a new thread and return its OO wrapper."""
        result = await self.rpc.request_typed(
            "thread/start",
            merge_params(params, **overrides),
            ThreadResult,
        )
        return AsyncAppServerThread(self, result.thread)

    async def resume_thread(
        self,
        thread_id: str,
        params: protocol.ThreadResumeParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AsyncAppServerThread:
        """Resume an existing thread and return its OO wrapper."""
        payload = merge_params(params, threadId=thread_id, **overrides)
        result = await self.rpc.request_typed("thread/resume", payload, ThreadResult)
        return AsyncAppServerThread(self, result.thread)

    async def read_thread(
        self,
        thread_id: str,
        *,
        include_turns: bool = False,
    ) -> protocol.Thread:
        """Read a stored thread snapshot without resuming it."""
        result = await self.rpc.request_typed(
            "thread/read",
            merge_params(threadId=thread_id, includeTurns=include_turns),
            ThreadResult,
        )
        return result.thread

    async def list_threads(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> list[protocol.Thread]:
        """List stored threads and return only the thread data."""
        result = await self.rpc.request_typed(
            "thread/list",
            merge_params(params, **overrides),
            ThreadListResult,
        )
        return result.data

    async def list_threads_page(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> ThreadListResult:
        """List stored threads and return the full paginated response."""
        return await self.rpc.request_typed(
            "thread/list",
            merge_params(params, **overrides),
            ThreadListResult,
        )

    async def loaded_thread_ids(self) -> list[str]:
        """Return the ids of threads currently loaded in app-server memory."""
        result = await self.rpc.request_typed("thread/loaded/list", {}, LoadedThreadsResult)
        return result.data

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        """Register a handler for server-initiated JSON-RPC requests."""
        self.rpc.on_request(method, handler, request_model=request_model)
