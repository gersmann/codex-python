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
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        future: concurrent.futures.Future[_T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()


class RpcClient:
    def __init__(self, async_rpc: AsyncRpcClient, loop: _LoopThread) -> None:
        self._async_rpc = async_rpc
        self._loop = loop

    def request(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        return self._loop.run(self._async_rpc.request(method, params))

    def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT:
        return self._loop.run(self._async_rpc.request_typed(method, params, result_model))

    def notify(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> None:
        self._loop.run(self._async_rpc.notify(method, params))

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        async def async_handler(request: BaseModel) -> object:
            result = handler(request)
            if inspect.isawaitable(result):
                return await cast(Awaitable[object], result)
            return result

        self._async_rpc.on_request(method, async_handler, request_model=request_model)


class ServiceNamespace:
    def __init__(self, async_namespace: AsyncServiceNamespace, loop: _LoopThread) -> None:
        self._async_namespace = async_namespace
        self._loop = loop

    def call(
        self,
        suffix: str,
        params: BaseModel | Mapping[str, object] | None = None,
    ) -> object:
        return self._loop.run(self._async_namespace.call(suffix, params))


class TurnStream:
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
        self._loop.run(self._async_stream.wait())
        return self

    def collect(self) -> TurnStream:
        return self.wait()

    def steer(self, input: TurnInput, **overrides: object) -> TurnIdResult:
        return self._loop.run(self._async_stream.steer(input, **overrides))

    def interrupt(self) -> EmptyResult:
        return self._loop.run(self._async_stream.interrupt())

    def close(self) -> None:
        self._loop.run(self._async_stream.close())


class AppServerThread:
    def __init__(self, async_thread: AsyncAppServerThread, loop: _LoopThread) -> None:
        self._async_thread = async_thread
        self._loop = loop

    @property
    def id(self) -> str:
        return self._async_thread.id

    @property
    def snapshot(self) -> protocol.Thread:
        return self._async_thread.snapshot

    def refresh(self, *, include_turns: bool = False) -> protocol.Thread:
        return self._loop.run(self._async_thread.refresh(include_turns=include_turns))

    def run(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> TurnStream:
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
        return self._loop.run(self._async_thread.run_text(input, params, **overrides))

    def run_json(
        self,
        input: TurnInput,
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> object:
        return self._loop.run(self._async_thread.run_json(input, params, **overrides))

    def run_model(
        self,
        input: TurnInput,
        model_type: type[_ModelT],
        params: protocol.TurnStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> _ModelT:
        return self._loop.run(self._async_thread.run_model(input, model_type, params, **overrides))

    def review(
        self,
        *,
        target: BaseModel | Mapping[str, object],
        delivery: str = "inline",
        params: Mapping[str, object] | None = None,
        **overrides: object,
    ) -> TurnStream:
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
        return AppServerThread(self._loop.run(self._async_thread.fork(params)), self._loop)

    def archive(self) -> EmptyResult:
        return self._loop.run(self._async_thread.archive())

    def unarchive(self) -> protocol.Thread:
        return self._loop.run(self._async_thread.unarchive())

    def rollback(self, num_turns: int) -> protocol.Thread:
        return self._loop.run(self._async_thread.rollback(num_turns))

    def compact(self) -> EmptyResult:
        return self._loop.run(self._async_thread.compact())

    def set_name(self, name: str) -> EmptyResult:
        return self._loop.run(self._async_thread.set_name(name))

    def unsubscribe(self) -> object:
        return self._loop.run(self._async_thread.unsubscribe())


class AppServerClient:
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
        try:
            self._loop.run(self._async_client.close())
        finally:
            self._loop.close()

    def start_thread(
        self,
        params: protocol.ThreadStartParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> AppServerThread:
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
        return AppServerThread(
            self._loop.run(self._async_client.resume_thread(thread_id, params, **overrides)),
            self._loop,
        )

    def read_thread(self, thread_id: str, *, include_turns: bool = False) -> protocol.Thread:
        return self._loop.run(
            self._async_client.read_thread(thread_id, include_turns=include_turns)
        )

    def list_threads(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> list[protocol.Thread]:
        return self._loop.run(self._async_client.list_threads(params, **overrides))

    def list_threads_page(
        self,
        params: protocol.ThreadListParams | Mapping[str, object] | None = None,
        **overrides: object,
    ) -> ThreadListResult:
        return self._loop.run(self._async_client.list_threads_page(params, **overrides))

    def loaded_thread_ids(self) -> list[str]:
        return self._loop.run(self._async_client.loaded_thread_ids())

    def on_request(
        self,
        method: str,
        handler: RequestHandler,
        *,
        request_model: type[BaseModel] | None = None,
    ) -> None:
        self.rpc.on_request(method, handler, request_model=request_model)
