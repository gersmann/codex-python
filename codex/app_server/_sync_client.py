"""Sync public client surface for `codex app-server`."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from collections.abc import Awaitable, Coroutine, Mapping
from threading import Thread
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from codex.app_server._async_client import (
    AsyncAppServerClient,
    AsyncAppServerThread,
    AsyncRpcClient,
    AsyncServiceNamespace,
    AsyncTurnStream,
)
from codex.app_server._helpers import Notification, RequestHandler, TurnInput
from codex.app_server.models import EmptyResult, ThreadListResult, TurnIdResult
from codex.app_server.options import AppServerInitializeOptions, AppServerProcessOptions
from codex.protocol import types as protocol

_T = TypeVar("_T")
_ModelT = TypeVar("_ModelT", bound=BaseModel)


class _LoopThread:
    """Run the async app-server client behind a dedicated event loop thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Run a coroutine on the loop thread and return its result."""
        future: concurrent.futures.Future[_T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        """Stop the loop thread."""
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()


class RpcClient:
    """Synchronous wrapper over `AsyncRpcClient`."""

    def __init__(self, async_rpc: AsyncRpcClient, loop: _LoopThread) -> None:
        self._async_rpc = async_rpc
        self._loop = loop

    def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        """Send a raw JSON-RPC request and return the decoded result."""
        return self._loop.run(self._async_rpc.request(method, params))

    def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        """Send a request and validate the response with a Pydantic model."""
        return self._loop.run(self._async_rpc.request_typed(method, params, result_model))

    def notify(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> None:
        """Send a JSON-RPC notification."""
        self._loop.run(self._async_rpc.notify(method, params))

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        """Register a handler for server-initiated JSON-RPC requests."""

        async def async_handler(request: BaseModel) -> object:
            result = handler(request)
            if inspect.isawaitable(result):
                return await cast(Awaitable[object], result)
            return result

        self._async_rpc.on_request(method, async_handler, request_model=request_model)


class ServiceNamespace:
    """Synchronous helper for calling methods under a shared prefix."""

    def __init__(self, async_namespace: AsyncServiceNamespace, loop: _LoopThread) -> None:
        self._async_namespace = async_namespace
        self._loop = loop

    def call(
        self,
        suffix: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        """Call a method under the namespace prefix."""
        return self._loop.run(self._async_namespace.call(suffix, params))


class TurnStream:
    """Synchronous iterator over protocol-native notifications for a single turn."""

    def __init__(self, async_stream: AsyncTurnStream, loop: _LoopThread) -> None:
        self._async_stream = async_stream
        self._loop = loop

    def __iter__(self) -> TurnStream:
        return self

    def __next__(self) -> Notification:
        try:
            return self._loop.run(self._async_stream.__anext__())
        except StopAsyncIteration as exc:
            raise StopIteration from exc

    @property
    def initial_turn(self) -> protocol.Turn:
        """Return the initial turn snapshot from the start response."""
        return self._async_stream.initial_turn

    @property
    def final_turn(self) -> protocol.Turn | None:
        """Return the final turn snapshot after completion."""
        return self._async_stream.final_turn

    @property
    def final_text(self) -> str:
        """Return the final assistant message text collected so far."""
        return self._async_stream.final_text

    @property
    def final_message(self) -> protocol.AgentMessageThreadItem | None:
        """Return the final assistant message item when available."""
        return self._async_stream.final_message

    @property
    def items(self) -> list[protocol.ThreadItem]:
        """Return the latest completed state for turn items seen so far."""
        return self._async_stream.items

    @property
    def usage(self) -> protocol.ThreadTokenUsage | None:
        """Return the latest thread token usage update for this turn."""
        return self._async_stream.usage

    @property
    def text_deltas(self) -> tuple[str, ...]:
        """Return the streamed agent text deltas received so far."""
        return self._async_stream.text_deltas

    def final_json(self) -> object:
        """Parse the final assistant message text as JSON."""
        return self._async_stream.final_json()

    def final_model(self, model_type: type[_ModelT]) -> _ModelT:
        """Validate the final assistant message text with a Pydantic model."""
        return self._async_stream.final_model(model_type)

    def wait(self) -> TurnStream:
        """Consume the stream to completion and return `self`."""
        self._loop.run(self._async_stream.wait())
        return self

    def collect(self) -> TurnStream:
        """Alias for `wait()`."""
        return self.wait()

    def steer(self, input: TurnInput, **overrides: object) -> TurnIdResult:
        """Append additional user input to the in-flight turn."""
        return self._loop.run(self._async_stream.steer(input, **overrides))

    def interrupt(self) -> EmptyResult:
        """Interrupt the active turn."""
        return self._loop.run(self._async_stream.interrupt())

    def close(self) -> None:
        """Close the underlying notification subscription early."""
        self._loop.run(self._async_stream.close())


class AppServerThread:
    """Synchronous OO wrapper around a single app-server thread."""

    def __init__(self, async_thread: AsyncAppServerThread, loop: _LoopThread) -> None:
        self._async_thread = async_thread
        self._loop = loop

    @property
    def id(self) -> str:
        """Return the thread identifier."""
        return self._async_thread.id

    @property
    def snapshot(self) -> protocol.Thread:
        """Return the latest cached thread snapshot."""
        return self._async_thread.snapshot

    def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
        """Reload the stored thread snapshot from app-server."""
        return self._loop.run(self._async_thread.refresh(include_turns=include_turns))

    def run(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> TurnStream:
        """Start a turn and return the protocol-native notification stream."""
        return TurnStream(
            self._loop.run(self._async_thread.run(input, params, **overrides)),
            self._loop,
        )

    def run_text(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> str:
        """Run a turn and return only the final assistant text."""
        return self._loop.run(self._async_thread.run_text(input, params, **overrides))

    def run_json(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> object:
        """Run a turn and parse the final assistant text as JSON."""
        return self._loop.run(self._async_thread.run_json(input, params, **overrides))

    def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> _ModelT:
        """Run a turn and validate the final assistant text with `model_type`."""
        return self._loop.run(self._async_thread.run_model(input, model_type, params, **overrides))

    def review(
        self,
        *,
        target: BaseModel | Mapping[str, object],
        delivery: str = "inline",
        params: Mapping[str, object] | None = None,
        **overrides: object,
    ) -> TurnStream:
        """Start a review turn on this thread."""
        return TurnStream(
            self._loop.run(
                self._async_thread.review(
                    target=target,
                    delivery=delivery,
                    params=params,
                    **overrides,
                )
            ),
            self._loop,
        )

    def fork(
        self, params: protocol.ThreadForkParams | Mapping[str, object] | None = None
    ) -> AppServerThread:
        """Fork this thread and return the new thread object."""
        return AppServerThread(self._loop.run(self._async_thread.fork(params)), self._loop)

    def archive(self) -> EmptyResult:
        """Archive the thread."""
        return self._loop.run(self._async_thread.archive())

    def unarchive(self) -> protocol.Thread:
        """Restore an archived thread and refresh the local snapshot."""
        return self._loop.run(self._async_thread.unarchive())

    def rollback(self, num_turns: int) -> protocol.Thread:
        """Roll back the last `num_turns` turns."""
        return self._loop.run(self._async_thread.rollback(num_turns))

    def compact(self) -> EmptyResult:
        """Trigger thread compaction."""
        return self._loop.run(self._async_thread.compact())

    def set_name(self, name: str) -> EmptyResult:
        """Set the user-facing thread name."""
        return self._loop.run(self._async_thread.set_name(name))

    def unsubscribe(self) -> object:
        """Unsubscribe this connection from the loaded thread."""
        return self._loop.run(self._async_thread.unsubscribe())


class AppServerClient:
    """Synchronous client for `codex app-server`."""

    def __init__(self, async_client: AsyncAppServerClient, loop: _LoopThread) -> None:
        self._async_client = async_client
        self._loop = loop
        self.rpc = RpcClient(async_client.rpc, loop)
        self.models = ServiceNamespace(async_client.models, loop)
        self.account = ServiceNamespace(async_client.account, loop)
        self.config = ServiceNamespace(async_client.config, loop)
        self.apps = ServiceNamespace(async_client.apps, loop)
        self.skills = ServiceNamespace(async_client.skills, loop)
        self.mcp_servers = ServiceNamespace(async_client.mcp_servers, loop)
        self.feedback = ServiceNamespace(async_client.feedback, loop)
        self.experimental_features = ServiceNamespace(async_client.experimental_features, loop)
        self.collaboration_modes = ServiceNamespace(async_client.collaboration_modes, loop)
        self.windows_sandbox = ServiceNamespace(async_client.windows_sandbox, loop)

    @classmethod
    def connect_stdio(
        cls,
        process_options: AppServerProcessOptions | None = None,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AppServerClient:
        """Start `codex app-server` over stdio and initialize the session."""
        loop = _LoopThread()
        try:
            async_client = loop.run(
                AsyncAppServerClient.connect_stdio(process_options, initialize_options)
            )
        except Exception:
            loop.close()
            raise
        return cls(async_client, loop)

    @classmethod
    def connect_websocket(
        cls,
        url: str,
        initialize_options: AppServerInitializeOptions | None = None,
    ) -> AppServerClient:
        """Connect to an app-server websocket endpoint and initialize the session."""
        loop = _LoopThread()
        try:
            async_client = loop.run(AsyncAppServerClient.connect_websocket(url, initialize_options))
        except Exception:
            loop.close()
            raise
        return cls(async_client, loop)

    def __enter__(self) -> AppServerClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = (exc_type, exc, tb)
        self.close()

    def close(self) -> None:
        """Close the app-server session and its loop thread."""
        try:
            self._loop.run(self._async_client.close())
        finally:
            self._loop.close()

    def start_thread(
        self,
        params: protocol.ThreadStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AppServerThread:
        """Create a new thread and return its OO wrapper."""
        return AppServerThread(
            self._loop.run(self._async_client.start_thread(params, **overrides)),
            self._loop,
        )

    def resume_thread(
        self,
        thread_id: str,
        params: protocol.ThreadResumeParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AppServerThread:
        """Resume an existing thread and return its OO wrapper."""
        return AppServerThread(
            self._loop.run(self._async_client.resume_thread(thread_id, params, **overrides)),
            self._loop,
        )

    def read_thread(self, thread_id: str, *, include_turns: bool = False) -> protocol.Thread:
        """Read a stored thread snapshot without resuming it."""
        return self._loop.run(
            self._async_client.read_thread(thread_id, include_turns=include_turns)
        )

    def list_threads(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> list[protocol.Thread]:
        """List stored threads and return only the thread data."""
        return self._loop.run(self._async_client.list_threads(params, **overrides))

    def list_threads_page(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> ThreadListResult:
        """List stored threads and return the full paginated response."""
        return self._loop.run(self._async_client.list_threads_page(params, **overrides))

    def loaded_thread_ids(self) -> list[str]:
        """Return the ids of threads currently loaded in app-server memory."""
        return self._loop.run(self._async_client.loaded_thread_ids())

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        """Register a handler for server-initiated JSON-RPC requests."""
        self.rpc.on_request(method, handler, request_model=request_model)
