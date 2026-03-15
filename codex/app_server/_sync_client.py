"""Sync client entrypoints for `codex app-server`."""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from collections.abc import Callable, Collection, Coroutine, Mapping
from contextlib import suppress
from threading import Thread
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from codex.app_server._async_client import AsyncAppServerClient, AsyncRpcClient
from codex.app_server._protocol_helpers import RequestHandler
from codex.app_server._sync_services import (
    _AccountClient,
    _AppsClient,
    _CommandClient,
    _ConfigClient,
    _ExternalAgentConfigClient,
    _FeedbackClient,
    _McpServersClient,
    _ModelsClient,
    _SkillsClient,
    _WindowsSandboxClient,
)
from codex.app_server._sync_support import _SyncRunner
from codex.app_server._sync_threads import (
    AppServerThread,
    EventsClient,
    _AsyncThreadLike,
)
from codex.app_server.models import ThreadListResult
from codex.app_server.options import (
    AppServerInitializeOptions,
    AppServerProcessOptions,
    AppServerThreadListOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerWebSocketOptions,
)
from codex.protocol import types as protocol

_T = TypeVar("_T")
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_RequestT = TypeVar("_RequestT", bound=BaseModel)

__all__ = [
    "AppServerClient",
    "AppServerThread",
    "EventsClient",
    "RpcClient",
]


class _LoopThread:
    """Run the async app-server client behind a dedicated event loop thread."""

    _RESULT_TIMEOUT = 0.05
    _SHUTDOWN_TIMEOUT = 3.0

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True)
        self._closed = False
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.run_until_complete(self._finalize_loop())
            self._loop.close()

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        future = self._submit(coro)
        try:
            return self._wait_for_future_result(future)
        except KeyboardInterrupt:
            future.cancel()
            with suppress(concurrent.futures.CancelledError, concurrent.futures.TimeoutError):
                future.result(timeout=self._RESULT_TIMEOUT)
            raise

    def close(self) -> None:
        self.shutdown()

    def shutdown(
        self,
        cleanup_coro: Coroutine[Any, Any, object] | None = None,
        *,
        timeout: float | None = None,
    ) -> bool:
        if self._closed:
            return False
        interrupted = False
        deadline = time.monotonic() + (self._SHUTDOWN_TIMEOUT if timeout is None else timeout)
        cleanup_error: BaseException | None = None

        cleanup_future: concurrent.futures.Future[object] | None = None
        if cleanup_coro is not None:
            cleanup_future = self._submit(cleanup_coro)
            interrupted, cleanup_error = self._drain_future(cleanup_future, deadline)
            if cleanup_error is not None and not isinstance(
                cleanup_error, concurrent.futures.CancelledError
            ):
                cleanup_future = None

        cancel_future = self._submit(self._cancel_pending_tasks())
        cancel_interrupted, cancel_error = self._drain_future(cancel_future, deadline)
        interrupted = interrupted or cancel_interrupted
        if cleanup_error is None and cancel_error is not None:
            cleanup_error = cancel_error
        self._closed = True

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=max(0.0, deadline - time.monotonic()))

        if cleanup_error is not None and not isinstance(
            cleanup_error, concurrent.futures.CancelledError
        ):
            raise cleanup_error
        return interrupted

    def _submit(self, coro: Coroutine[Any, Any, _T]) -> concurrent.futures.Future[_T]:
        if self._closed:
            coro.close()
            raise RuntimeError("loop thread is closed")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _wait_for_future_result(self, future: concurrent.futures.Future[_T]) -> _T:
        return future.result()

    def _drain_future(
        self,
        future: concurrent.futures.Future[Any],
        deadline: float,
    ) -> tuple[bool, BaseException | None]:
        interrupted = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                future.cancel()
                return interrupted, concurrent.futures.TimeoutError()
            try:
                done, _ = concurrent.futures.wait(
                    {future},
                    timeout=remaining,
                    return_when=concurrent.futures.ALL_COMPLETED,
                )
            except KeyboardInterrupt:
                interrupted = True
                future.cancel()
                continue
            if not done:
                future.cancel()
                return interrupted, concurrent.futures.TimeoutError()
            try:
                future.result()
                return interrupted, None
            except concurrent.futures.CancelledError as exc:
                return interrupted, exc
            except Exception as exc:  # pragma: no cover - defensive propagation
                return interrupted, exc

    async def _cancel_pending_tasks(self) -> None:
        current = asyncio.current_task()
        pending = [task for task in asyncio.all_tasks() if task is not current]
        for task in pending:
            task.cancel()
        if pending:
            results = await asyncio.gather(*pending, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(
                    result, asyncio.CancelledError
                ):
                    raise result

    async def _finalize_loop(self) -> None:
        await self._cancel_pending_tasks()
        await self._loop.shutdown_asyncgens()


class RpcClient(_SyncRunner):
    """Synchronous wrapper over `AsyncRpcClient`."""

    def __init__(self, async_rpc: AsyncRpcClient, loop: _LoopThread) -> None:
        super().__init__(loop.run)
        self._async_rpc = async_rpc

    def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        return self._run(self._async_rpc.request(method, params))

    def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        return self._run(self._async_rpc.request_typed(method, params, result_model))

    def notify(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> None:
        self._run(self._async_rpc.notify(method, params))

    def on_request(
        self,
        method: str,
        handler: RequestHandler[_RequestT],
        *,
        request_model: type[_RequestT] | None = None,
    ) -> None:
        self._async_rpc.on_request(method, handler, request_model=request_model)


class AppServerClient(_SyncRunner):
    """Synchronous client for `codex app-server`."""

    def __init__(self, async_client: AsyncAppServerClient, loop: _LoopThread) -> None:
        super().__init__(loop.run)
        self._async_client = async_client
        self._loop = loop
        self.rpc = RpcClient(async_client.rpc, loop)
        self.events = EventsClient(async_client.events, self._run)
        self.models = _ModelsClient(async_client.models, self._run)
        self.apps = _AppsClient(async_client.apps, self._run)
        self.skills = _SkillsClient(async_client.skills, self._run)
        self.account = _AccountClient(async_client.account, self._run)
        self.config = _ConfigClient(async_client.config, self._run)
        self.mcp_servers = _McpServersClient(async_client.mcp_servers, self._run)
        self.feedback = _FeedbackClient(async_client.feedback, self._run)
        self.command = _CommandClient(async_client.command, self._run)
        self.external_agent_config = _ExternalAgentConfigClient(
            async_client.external_agent_config,
            self._run,
        )
        self.windows_sandbox = _WindowsSandboxClient(async_client.windows_sandbox, self._run)

    @classmethod
    def connect_stdio(
        cls,
        process_options: AppServerProcessOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AppServerClient:
        loop = _LoopThread()
        async_client: AsyncAppServerClient | None = None
        try:
            async_client = loop.run(
                AsyncAppServerClient.connect_stdio(process_options, initialize_options)
            )
        finally:
            if async_client is None:
                loop.close()
        return cls(async_client, loop)

    @classmethod
    def connect_websocket(
        cls,
        url: str,
        websocket_options: AppServerWebSocketOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AppServerClient:
        loop = _LoopThread()
        async_client: AsyncAppServerClient | None = None
        try:
            async_client = loop.run(
                AsyncAppServerClient.connect_websocket(
                    url,
                    websocket_options,
                    initialize_options,
                )
            )
        finally:
            if async_client is None:
                loop.close()
        return cls(async_client, loop)

    def __enter__(self) -> AppServerClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = (exc_type, exc, tb)
        try:
            interrupted = self._loop.shutdown(self._async_client.close())
        except KeyboardInterrupt:
            if exc_type is None:
                raise
            return
        except Exception:
            if exc_type is None:
                raise
            return
        if interrupted and exc_type is None:
            raise KeyboardInterrupt

    def close(self) -> None:
        interrupted = self._loop.shutdown(self._async_client.close())
        if interrupted:
            raise KeyboardInterrupt

    def start_thread(
        self,
        options: AppServerThreadStartOptions | None = None,
        *,
        tools: Collection[Callable[..., object]] | None = None,
    ) -> AppServerThread:
        return AppServerThread(
            cast(
                _AsyncThreadLike, self._run(self._async_client.start_thread(options, tools=tools))
            ),
            self._run,
        )

    def resume_thread(
        self,
        thread_id: str,
        options: AppServerThreadResumeOptions | None = None,
    ) -> AppServerThread:
        return AppServerThread(
            cast(
                _AsyncThreadLike,
                self._run(self._async_client.resume_thread(thread_id, options)),
            ),
            self._run,
        )

    def read_thread(self, thread_id: str, *, include_turns: bool = False) -> protocol.Thread:
        return self._run(self._async_client.read_thread(thread_id, include_turns=include_turns))

    def list_threads(
        self,
        options: AppServerThreadListOptions | None = None,
    ) -> list[protocol.Thread]:
        return self._run(self._async_client.list_threads(options))

    def list_threads_page(
        self,
        options: AppServerThreadListOptions | None = None,
    ) -> ThreadListResult:
        return self._run(self._async_client.list_threads_page(options))

    def loaded_thread_ids(self) -> list[str]:
        return self._run(self._async_client.loaded_thread_ids())

    def on_request(
        self,
        method: str,
        handler: RequestHandler[_RequestT],
        *,
        request_model: type[_RequestT] | None = None,
    ) -> None:
        self.rpc.on_request(method, handler, request_model=request_model)
