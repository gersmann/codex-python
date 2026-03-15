from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Mapping
from typing import Any, Protocol

from codex._binary import bundled_codex_path
from codex._runtime import build_child_env, resolve_codex_path, serialize_config_overrides
from codex.app_server._types import JsonObject
from codex.app_server.errors import (
    AppServerClosedError,
    AppServerConnectionError,
    AppServerProtocolError,
)
from codex.app_server.options import AppServerProcessOptions, AppServerWebSocketOptions

STDIO_STREAM_LIMIT_BYTES = 4 * 1024 * 1024


class AsyncMessageTransport(Protocol):
    async def start(self) -> None: ...

    async def send(self, message: JsonObject) -> None: ...

    async def receive(self) -> JsonObject | None: ...

    async def close(self) -> None: ...


def _resolve_codex_path(executable_path: str | None) -> str:
    return resolve_codex_path(
        executable_path,
        bundled_path=bundled_codex_path,
        which=shutil.which,
        error_type=AppServerConnectionError,
    )


def _build_env(options: AppServerProcessOptions) -> dict[str, str]:
    env_override = os.environ if options.env is None else options.env
    return build_child_env(
        env_override,
        base_url=options.base_url,
        api_key=options.api_key,
    )


class AsyncStdioTransport:
    def __init__(self, options: AppServerProcessOptions | None = None) -> None:
        self._options = options or AppServerProcessOptions()
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._stderr_lines: list[str] = []

    async def start(self) -> None:
        if self._process is not None:
            return
        executable = _resolve_codex_path(self._options.codex_path_override)
        command = [executable, "app-server"]
        if self._options.analytics_default_enabled:
            command.append("--analytics-default-enabled")
        if self._options.config is not None:
            for override in serialize_config_overrides(self._options.config):
                command.extend(["--config", override])

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=STDIO_STREAM_LIMIT_BYTES,
                env=_build_env(self._options),
            )
        except OSError as exc:
            raise AppServerConnectionError(f"Failed to start codex app-server: {exc}") from exc

        if process.stdin is None or process.stdout is None or process.stderr is None:
            process.kill()
            await process.wait()
            raise AppServerConnectionError("codex app-server did not expose stdio pipes")

        self._process = process
        self._stderr_task = asyncio.create_task(self._drain_stderr(process.stderr))

    async def _drain_stderr(self, stderr: asyncio.StreamReader) -> None:
        while True:
            line = await _readline_with_limit_error(stderr, stream_name="stderr")
            if line == b"":
                break
            self._stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())

    async def send(self, message: JsonObject) -> None:
        if self._process is None or self._process.stdin is None:
            raise AppServerClosedError("app-server stdio transport is not running")
        payload = json.dumps(message, separators=(",", ":")) + "\n"
        try:
            self._process.stdin.write(payload.encode("utf-8"))
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise AppServerClosedError("app-server stdin is closed") from exc

    async def receive(self) -> JsonObject | None:
        if self._process is None or self._process.stdout is None:
            raise AppServerClosedError("app-server stdio transport is not running")
        line = await _readline_with_limit_error(self._process.stdout, stream_name="stdout")
        if line == b"":
            return None
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AppServerProtocolError(
                f"Failed to decode app-server JSON message: {line!r}"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise AppServerProtocolError(
                f"Expected app-server message object, received {type(parsed).__name__}"
            )
        return dict(parsed)

    async def close(self) -> None:
        process = self._process
        if process is None:
            return
        self._process = None
        if process.stdin is not None:
            process.stdin.close()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except TimeoutError:
                process.kill()
                await process.wait()
        if self._stderr_task is not None:
            await self._stderr_task
            self._stderr_task = None


class AsyncWebSocketTransport:
    def __init__(
        self,
        url: str,
        options: AppServerWebSocketOptions | None = None,
    ) -> None:
        self._url = url
        self._options = options or AppServerWebSocketOptions()
        self._connection: Any | None = None
        self._connection_closed_ok_types: tuple[type[BaseException], ...] = ()
        self._connection_closed_error_types: tuple[type[BaseException], ...] = ()

    async def start(self) -> None:
        if self._connection is not None:
            return
        websockets = _load_websockets_module()
        self._configure_websocket_exception_types(websockets)
        connect_kwargs = self._options.to_connect_kwargs()
        try:
            self._connection = await websockets.connect(
                self._url,
                **connect_kwargs,
            )
        except Exception as exc:
            raise AppServerConnectionError(f"Failed to connect to {self._url}: {exc}") from exc

    async def send(self, message: JsonObject) -> None:
        if self._connection is None:
            raise AppServerClosedError("app-server websocket transport is not connected")
        try:
            await self._connection.send(json.dumps(message, separators=(",", ":")))
        except self._connection_closed_ok_types as exc:
            self._connection = None
            raise AppServerClosedError("app-server websocket connection is closed") from exc
        except self._connection_closed_error_types as exc:
            self._connection = None
            raise AppServerConnectionError(f"app-server websocket send failed: {exc}") from exc
        except Exception as exc:
            self._connection = None
            raise AppServerConnectionError(f"app-server websocket send failed: {exc}") from exc

    async def receive(self) -> JsonObject | None:
        if self._connection is None:
            raise AppServerClosedError("app-server websocket transport is not connected")
        try:
            payload = await self._connection.recv()
        except self._connection_closed_ok_types:
            self._connection = None
            return None
        except self._connection_closed_error_types as exc:
            self._connection = None
            raise AppServerConnectionError(f"app-server websocket receive failed: {exc}") from exc
        except Exception as exc:
            self._connection = None
            raise AppServerConnectionError(f"app-server websocket receive failed: {exc}") from exc
        if not isinstance(payload, str):
            raise AppServerProtocolError("Expected websocket text frame from app-server")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AppServerProtocolError(
                f"Failed to decode app-server websocket message: {payload!r}"
            ) from exc
        if not isinstance(parsed, Mapping):
            raise AppServerProtocolError(
                f"Expected app-server message object, received {type(parsed).__name__}"
            )
        return dict(parsed)

    async def close(self) -> None:
        if self._connection is None:
            return
        connection = self._connection
        self._connection = None
        await connection.close()

    def _configure_websocket_exception_types(self, websockets: Any) -> None:
        exceptions = getattr(websockets, "exceptions", None)
        if exceptions is None:
            self._connection_closed_ok_types = ()
            self._connection_closed_error_types = ()
            return
        connection_closed_ok = getattr(exceptions, "ConnectionClosedOK", None)
        connection_closed_error = getattr(exceptions, "ConnectionClosedError", None)
        self._connection_closed_ok_types = _exception_types(connection_closed_ok)
        self._connection_closed_error_types = _exception_types(connection_closed_error)


def _load_websockets_module() -> Any:
    try:
        import websockets
    except ImportError as exc:
        raise AppServerConnectionError(
            "websocket transport requires the optional `websockets` package; "
            "install codex-python[websocket]"
        ) from exc
    return websockets


def _exception_types(candidate: object) -> tuple[type[BaseException], ...]:
    if isinstance(candidate, type) and issubclass(candidate, BaseException):
        return (candidate,)
    return ()


async def _readline_with_limit_error(
    stream: asyncio.StreamReader,
    *,
    stream_name: str,
) -> bytes:
    try:
        return await stream.readline()
    except ValueError as exc:
        raise AppServerProtocolError(
            "app-server stdio "
            f"{stream_name} line exceeded configured limit of {STDIO_STREAM_LIMIT_BYTES} bytes"
        ) from exc
