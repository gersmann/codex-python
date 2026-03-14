"""Async client entrypoints for `codex app-server`."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import TypeVar, cast

from pydantic import BaseModel

from codex.app_server._async_services import (
    AsyncAccountClient,
    AsyncAppsClient,
    AsyncCommandClient,
    AsyncConfigClient,
    AsyncExternalAgentConfigClient,
    AsyncFeedbackClient,
    AsyncMcpServersClient,
    AsyncModelsClient,
    AsyncSkillsClient,
    AsyncWindowsSandboxClient,
)
from codex.app_server._async_threads import AsyncAppServerThread as AsyncAppServerThread
from codex.app_server._async_threads import AsyncTurnStream as AsyncTurnStream
from codex.app_server._async_threads import _ThreadClient
from codex.app_server._protocol_helpers import RequestHandler
from codex.app_server._session import _AsyncNotificationSubscription, _AsyncSession
from codex.app_server.models import (
    InitializeResult,
    LoadedThreadsResult,
    ThreadListResult,
    ThreadResult,
)
from codex.app_server.options import (
    AppServerInitializeOptions,
    AppServerProcessOptions,
    AppServerThreadListOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerWebSocketOptions,
)
from codex.app_server.transports import (
    AsyncMessageTransport,
    AsyncStdioTransport,
    AsyncWebSocketTransport,
)
from codex.protocol import types as protocol

_ModelT = TypeVar("_ModelT", bound=BaseModel)
_RequestT = TypeVar("_RequestT", bound=BaseModel)

__all__ = [
    "AsyncAppServerClient",
    "AsyncAppServerThread",
    "AsyncEventsClient",
    "AsyncRpcClient",
    "AsyncTurnStream",
]


class AsyncRpcClient:
    """Low-level async JSON-RPC access to app-server methods."""

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
        handler: RequestHandler[_RequestT],
        *,
        request_model: type[_RequestT] | None = None,
    ) -> None:
        self._session.on_request(method, handler, request_model=request_model)


class AsyncEventsClient:
    """Advanced subscription access to connection-wide notifications."""

    def __init__(self, session: _AsyncSession) -> None:
        self._session = session

    def subscribe(self, methods: Collection[str] | None = None) -> _AsyncNotificationSubscription:
        return self._session.subscribe_notifications(methods)


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
        self.models = AsyncModelsClient(self.rpc)
        self.apps = AsyncAppsClient(self.rpc)
        self.skills = AsyncSkillsClient(self.rpc)
        self.account = AsyncAccountClient(self.rpc)
        self.config = AsyncConfigClient(self.rpc)
        self.mcp_servers = AsyncMcpServersClient(self.rpc)
        self.feedback = AsyncFeedbackClient(self.rpc)
        self.command = AsyncCommandClient(self.rpc)
        self.external_agent_config = AsyncExternalAgentConfigClient(self.rpc)
        self.windows_sandbox = AsyncWindowsSandboxClient(self.rpc)

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
        websocket_options: AppServerWebSocketOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AsyncAppServerClient:
        """Connect to an app-server websocket endpoint and initialize the session."""
        client = cls(AsyncWebSocketTransport(url, websocket_options), initialize_options)
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
        options: AppServerThreadStartOptions | None = None,
    ) -> AsyncAppServerThread:
        result = await self.rpc.request_typed(
            "thread/start",
            (options or AppServerThreadStartOptions()).to_params(),
            ThreadResult,
        )
        return AsyncAppServerThread(cast(_ThreadClient, self), result.thread)

    async def resume_thread(
        self,
        thread_id: str,
        options: AppServerThreadResumeOptions | None = None,
    ) -> AsyncAppServerThread:
        payload = (options or AppServerThreadResumeOptions()).to_params(thread_id=thread_id)
        result = await self.rpc.request_typed("thread/resume", payload, ThreadResult)
        return AsyncAppServerThread(cast(_ThreadClient, self), result.thread)

    async def read_thread(
        self,
        thread_id: str,
        *,
        include_turns: bool = False,
    ) -> protocol.Thread:
        result = await self.rpc.request_typed(
            "thread/read",
            protocol.ThreadReadParams(threadId=thread_id, includeTurns=include_turns),
            ThreadResult,
        )
        return result.thread

    async def list_threads(
        self,
        options: AppServerThreadListOptions | None = None,
    ) -> list[protocol.Thread]:
        result = await self.rpc.request_typed(
            "thread/list",
            (options or AppServerThreadListOptions()).to_params(),
            ThreadListResult,
        )
        return result.data

    async def list_threads_page(
        self,
        options: AppServerThreadListOptions | None = None,
    ) -> ThreadListResult:
        return await self.rpc.request_typed(
            "thread/list",
            (options or AppServerThreadListOptions()).to_params(),
            ThreadListResult,
        )

    async def loaded_thread_ids(self) -> list[str]:
        result = await self.rpc.request_typed("thread/loaded/list", {}, LoadedThreadsResult)
        return result.data

    def on_request(
        self,
        method: str,
        handler: RequestHandler[_RequestT],
        *,
        request_model: type[_RequestT] | None = None,
    ) -> None:
        self.rpc.on_request(method, handler, request_model=request_model)
