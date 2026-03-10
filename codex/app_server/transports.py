from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from codex._binary import bundled_codex_path
from codex.app_server.errors import (
    AppServerClosedError,
    AppServerConnectionError,
    AppServerProtocolError,
)
from codex.app_server.options import AppServerProcessOptions
from codex.exec import INTERNAL_ORIGINATOR_ENV, PYTHON_SDK_ORIGINATOR, serialize_config_overrides

JsonObject = dict[str, Any]


class AsyncMessageTransport(Protocol):
    async def start(self) -> None: ...

    async def send(self, message: JsonObject) -> None: ...

    async def receive(self) -> JsonObject | None: ...

    async def close(self) -> None: ...


def _resolve_codex_path(executable_path: str | None) -> str:
    if executable_path is not None:
        return str(Path(executable_path))
    try:
        return str(bundled_codex_path())
    except Exception as bundled_error:
        system_codex = shutil.which("codex")
        if system_codex is None:
            raise AppServerConnectionError(
                f"{bundled_error} Also failed to find `codex` on PATH."
            ) from bundled_error
        return system_codex


def _build_env(options: AppServerProcessOptions) -> dict[str, str]:
    env = os.environ.copy() if options.env is None else dict(options.env)
    if INTERNAL_ORIGINATOR_ENV not in env:
        env[INTERNAL_ORIGINATOR_ENV] = PYTHON_SDK_ORIGINATOR
    if options.base_url is not None:
        env["OPENAI_BASE_URL"] = options.base_url
    if options.api_key is not None:
        env["CODEX_API_KEY"] = options.api_key
    return env


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
            line = await stderr.readline()
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
        line = await self._process.stdout.readline()
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
    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: Any | None = None

    async def start(self) -> None:
        if self._connection is not None:
            return
        try:
            import websockets
        except ImportError as exc:
            raise AppServerConnectionError(
                "websockets transport requires the `websockets` package"
            ) from exc
        try:
            self._connection = await websockets.connect(self._url)
        except Exception as exc:
            raise AppServerConnectionError(f"Failed to connect to {self._url}: {exc}") from exc

    async def send(self, message: JsonObject) -> None:
        if self._connection is None:
            raise AppServerClosedError("app-server websocket transport is not connected")
        await self._connection.send(json.dumps(message, separators=(",", ":")))

    async def receive(self) -> JsonObject | None:
        if self._connection is None:
            raise AppServerClosedError("app-server websocket transport is not connected")
        try:
            payload = await self._connection.recv()
        except Exception:
            return None
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
