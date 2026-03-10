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
    def __init__(self, session: _AsyncSession) -> None:
        self._session = session

    async def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        return await self._session.request(method, params)

    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        return await self._session.request_typed(method, params, result_model)

    async def notify(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> None:
        await self._session.notify(method, params)

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        self._session.on_request(method, handler, request_model=request_model)


class AsyncServiceNamespace:
    def __init__(self, rpc: AsyncRpcClient, prefix: str) -> None:
        self._rpc = rpc
        self._prefix = prefix

    async def call(
        self,
        suffix: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        method = f"{self._prefix}/{suffix}" if suffix else self._prefix
        return await self._rpc.request(method, params)


class AsyncEventsClient:
    def __init__(self, session: _AsyncSession) -> None:
        self._session = session

    def subscribe(self, methods: Collection[str] | None = None) -> _AsyncNotificationSubscription:
        return self._session.subscribe_notifications(methods)


class AsyncTurnStream:
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
        if self._done:
            return self
        async for _ in self:
            pass
        return self

    async def collect(self) -> AsyncTurnStream:
        return await self.wait()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._subscription.close()

    async def steer(self, input: TurnInput, **overrides: object) -> TurnIdResult:
        params = merge_params(
            None,
            threadId=self.thread_id,
            expectedTurnId=self.turn_id,
            input=normalize_turn_input(input),
            **overrides,
        )
        return await self._thread._client.rpc.request_typed("turn/steer", params, TurnIdResult)

    async def interrupt(self) -> EmptyResult:
        params = merge_params(threadId=self.thread_id, turnId=self.turn_id)
        return await self._thread._client.rpc.request_typed("turn/interrupt", params, EmptyResult)

    def final_json(self) -> object:
        return json.loads(self._require_final_message_text())

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        return model_type.model_validate_json(self._require_final_message_text())

    @property
    def text_deltas(self) -> tuple[str, ...]:
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
    def __init__(self, client: AsyncAppServerClient, snapshot: protocol.Thread) -> None:
        self._client = client
        self.snapshot = snapshot

    @property
    def id(self) -> str:
        return self.snapshot.id

    async def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
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
        stream = await self.run(input, params, **overrides)
        await stream.wait()
        return stream.final_text

    async def run_json(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> object:
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
        payload = merge_params(params, threadId=self.id)
        result = await self._client.rpc.request_typed("thread/fork", payload, ThreadResult)
        return AsyncAppServerThread(self._client, result.thread)

    async def archive(self) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/archive",
            merge_params(threadId=self.id),
            EmptyResult,
        )

    async def unarchive(self) -> protocol.Thread:
        result = await self._client.rpc.request_typed(
            "thread/unarchive",
            merge_params(threadId=self.id),
            ThreadResult,
        )
        self.snapshot = result.thread
        return self.snapshot

    async def rollback(self, num_turns: int) -> protocol.Thread:
        result = await self._client.rpc.request_typed(
            "thread/rollback",
            merge_params(threadId=self.id, numTurns=num_turns),
            ThreadResult,
        )
        self.snapshot = result.thread
        return self.snapshot

    async def compact(self) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/compact/start",
            merge_params(threadId=self.id),
            EmptyResult,
        )

    async def set_name(self, name: str) -> EmptyResult:
        return await self._client.rpc.request_typed(
            "thread/name/set",
            merge_params(threadId=self.id, name=name),
            EmptyResult,
        )

    async def unsubscribe(self) -> object:
        return await self._client.rpc.request("thread/unsubscribe", merge_params(threadId=self.id))


class AsyncAppServerClient:
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
        client = cls(AsyncStdioTransport(process_options), initialize_options)
        await client.start()
        return client

    @classmethod
    async def connect_websocket(
        cls,
        url: str,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AsyncAppServerClient:
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
        return await self._session.start()

    async def close(self) -> None:
        await self._session.close()

    async def start_thread(
        self,
        params: protocol.ThreadStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AsyncAppServerThread:
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
        payload = merge_params(params, threadId=thread_id, **overrides)
        result = await self.rpc.request_typed("thread/resume", payload, ThreadResult)
        return AsyncAppServerThread(self, result.thread)

    async def read_thread(
        self,
        thread_id: str,
        *,
        include_turns: bool = False,
    ) -> protocol.Thread:
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
        return await self.rpc.request_typed(
            "thread/list",
            merge_params(params, **overrides),
            ThreadListResult,
        )

    async def loaded_thread_ids(self) -> list[str]:
        result = await self.rpc.request_typed("thread/loaded/list", {}, LoadedThreadsResult)
        return result.data

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        self.rpc.on_request(method, handler, request_model=request_model)
