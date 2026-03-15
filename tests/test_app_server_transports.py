from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from codex._binary import BundledCodexNotFoundError
from codex.app_server.errors import (
    AppServerClosedError,
    AppServerConnectionError,
    AppServerProtocolError,
)
from codex.app_server.options import AppServerProcessOptions, AppServerWebSocketOptions
from codex.app_server.transports import (
    AsyncStdioTransport,
    AsyncWebSocketTransport,
    _build_env,
    _resolve_codex_path,
)


class _FakeStreamWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.closed = False
        self.raise_on_drain: Exception | None = None

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        if self.raise_on_drain is not None:
            raise self.raise_on_drain

    def close(self) -> None:
        self.closed = True


class _FakeStreamReader:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks[:]
        self.raise_on_readline: Exception | None = None

    async def readline(self) -> bytes:
        if self.raise_on_readline is not None:
            raise self.raise_on_readline
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _FakeProcess:
    def __init__(
        self,
        *,
        stdin: _FakeStreamWriter | None,
        stdout: _FakeStreamReader | None,
        stderr: _FakeStreamReader | None,
        returncode: int | None = None,
    ) -> None:
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.killed = False
        self.terminated = False
        self.wait_calls = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    async def wait(self) -> int:
        self.wait_calls += 1
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class _FakeWebSocketConnection:
    def __init__(self, recv_values: list[object] | None = None) -> None:
        self.recv_values = (recv_values or [])[:]
        self.sent: list[str] = []
        self.closed = False

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    async def recv(self) -> object:
        if not self.recv_values:
            raise RuntimeError("connection closed")
        value = self.recv_values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self) -> None:
        self.closed = True


class _FakeConnectionClosedOK(Exception):
    pass


class _FakeConnectionClosedError(Exception):
    pass


class _FakeWebSocketExceptions:
    ConnectionClosedOK = _FakeConnectionClosedOK
    ConnectionClosedError = _FakeConnectionClosedError


def test_resolve_codex_path_prefers_override() -> None:
    assert _resolve_codex_path("/tmp/custom-codex") == "/tmp/custom-codex"


def test_resolve_codex_path_falls_back_to_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "codex.app_server.transports.bundled_codex_path",
        lambda: (_ for _ in ()).throw(BundledCodexNotFoundError("missing bundled")),
    )
    monkeypatch.setattr("codex.app_server.transports.shutil.which", lambda _: "/usr/bin/codex")

    assert _resolve_codex_path(None) == "/usr/bin/codex"


def test_resolve_codex_path_raises_when_no_binary_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "codex.app_server.transports.bundled_codex_path",
        lambda: (_ for _ in ()).throw(BundledCodexNotFoundError("missing bundled")),
    )
    monkeypatch.setattr("codex.app_server.transports.shutil.which", lambda _: None)

    with pytest.raises(AppServerConnectionError, match="Also failed to find `codex` on PATH"):
        _resolve_codex_path(None)


def test_resolve_codex_path_preserves_non_missing_bundle_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "codex.app_server.transports.bundled_codex_path",
        lambda: (_ for _ in ()).throw(RuntimeError("permission denied")),
    )
    monkeypatch.setattr("codex.app_server.transports.shutil.which", lambda _: "/usr/bin/codex")

    with pytest.raises(RuntimeError, match="permission denied"):
        _resolve_codex_path(None)


def test_build_env_uses_override_without_parent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEAK_ME", "nope")
    env = _build_env(
        AppServerProcessOptions(
            env={"CUSTOM_ENV": "custom"},
            base_url="http://localhost:8080",
            api_key="test-key",
        )
    )

    assert env["CUSTOM_ENV"] == "custom"
    assert env["OPENAI_BASE_URL"] == "http://localhost:8080"
    assert env["CODEX_API_KEY"] == "test-key"
    assert env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "codex_sdk_py"
    assert "LEAK_ME" not in env


def test_build_env_preserves_existing_originator() -> None:
    env = _build_env(
        AppServerProcessOptions(
            env={"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "already-set"},
        )
    )

    assert env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "already-set"


def test_stdio_transport_start_builds_command_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    fake_process = _FakeProcess(
        stdin=_FakeStreamWriter(),
        stdout=_FakeStreamReader([]),
        stderr=_FakeStreamReader([]),
    )

    async def fake_create_subprocess_exec(*cmd: str, **kwargs: object) -> _FakeProcess:
        captured["cmd"] = list(cmd)
        captured["env"] = kwargs["env"]
        captured["limit"] = kwargs["limit"]
        return fake_process

    monkeypatch.setattr("codex.app_server.transports._resolve_codex_path", lambda _: "/tmp/codex")
    monkeypatch.setattr(
        "codex.app_server.transports.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    async def scenario() -> None:
        transport = AsyncStdioTransport(
            AppServerProcessOptions(
                base_url="http://localhost:8080",
                api_key="test-key",
                config={"approval_policy": "never"},
                analytics_default_enabled=True,
            )
        )
        await transport.start()
        await transport.close()

    asyncio.run(scenario())

    assert captured["cmd"] == [
        "/tmp/codex",
        "app-server",
        "--analytics-default-enabled",
        "--config",
        'approval_policy="never"',
    ]
    assert captured["env"]["OPENAI_BASE_URL"] == "http://localhost:8080"
    assert captured["env"]["CODEX_API_KEY"] == "test-key"
    assert captured["limit"] == 4 * 1024 * 1024


def test_stdio_transport_start_raises_on_spawn_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
        _ = (args, kwargs)
        raise OSError("boom")

    monkeypatch.setattr("codex.app_server.transports._resolve_codex_path", lambda _: "/tmp/codex")
    monkeypatch.setattr(
        "codex.app_server.transports.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    async def scenario() -> None:
        transport = AsyncStdioTransport()
        with pytest.raises(AppServerConnectionError, match="Failed to start codex app-server"):
            await transport.start()

    asyncio.run(scenario())


def test_stdio_transport_start_raises_when_pipes_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = _FakeProcess(stdin=None, stdout=None, stderr=None)

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
        _ = (args, kwargs)
        return fake_process

    monkeypatch.setattr("codex.app_server.transports._resolve_codex_path", lambda _: "/tmp/codex")
    monkeypatch.setattr(
        "codex.app_server.transports.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    async def scenario() -> None:
        transport = AsyncStdioTransport()
        with pytest.raises(AppServerConnectionError, match="did not expose stdio pipes"):
            await transport.start()

    asyncio.run(scenario())
    assert fake_process.killed is True


def test_stdio_transport_send_and_receive_round_trip() -> None:
    async def scenario() -> None:
        stdin = _FakeStreamWriter()
        stdout = _FakeStreamReader([b'{"method":"ping","params":{}}\n'])
        stderr = _FakeStreamReader([])
        transport = AsyncStdioTransport()
        transport._process = _FakeProcess(stdin=stdin, stdout=stdout, stderr=stderr)

        await transport.send({"method": "initialize", "params": {}})
        message = await transport.receive()

        assert stdin.buffer.decode("utf-8") == '{"method":"initialize","params":{}}\n'
        assert message == {"method": "ping", "params": {}}

    asyncio.run(scenario())


def test_stdio_transport_send_raises_when_closed() -> None:
    async def scenario() -> None:
        transport = AsyncStdioTransport()
        with pytest.raises(AppServerClosedError, match="is not running"):
            await transport.send({"method": "ping"})

    asyncio.run(scenario())


def test_stdio_transport_send_raises_when_pipe_is_broken() -> None:
    async def scenario() -> None:
        stdin = _FakeStreamWriter()
        stdin.raise_on_drain = BrokenPipeError()
        transport = AsyncStdioTransport()
        transport._process = _FakeProcess(
            stdin=stdin,
            stdout=_FakeStreamReader([]),
            stderr=_FakeStreamReader([]),
        )
        with pytest.raises(AppServerClosedError, match="stdin is closed"):
            await transport.send({"method": "ping"})

    asyncio.run(scenario())


def test_stdio_transport_receive_raises_for_invalid_json() -> None:
    async def scenario() -> None:
        transport = AsyncStdioTransport()
        transport._process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=_FakeStreamReader([b"not-json\n"]),
            stderr=_FakeStreamReader([]),
        )
        with pytest.raises(
            AppServerProtocolError, match="Failed to decode app-server JSON message"
        ):
            await transport.receive()

    asyncio.run(scenario())


def test_stdio_transport_receive_wraps_overlong_line_errors() -> None:
    async def scenario() -> None:
        stdout = _FakeStreamReader([])
        stdout.raise_on_readline = ValueError("Separator is not found, and chunk exceed the limit")
        transport = AsyncStdioTransport()
        transport._process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=stdout,
            stderr=_FakeStreamReader([]),
        )
        with pytest.raises(
            AppServerProtocolError,
            match=r"stdout line exceeded configured limit of 4194304 bytes",
        ):
            await transport.receive()

    asyncio.run(scenario())


def test_stdio_transport_receive_raises_for_non_object_payload() -> None:
    async def scenario() -> None:
        transport = AsyncStdioTransport()
        transport._process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=_FakeStreamReader([b'["oops"]\n']),
            stderr=_FakeStreamReader([]),
        )
        with pytest.raises(AppServerProtocolError, match="Expected app-server message object"):
            await transport.receive()

    asyncio.run(scenario())


def test_stdio_transport_close_terminates_and_waits() -> None:
    async def scenario() -> None:
        process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=_FakeStreamReader([]),
            stderr=_FakeStreamReader([b"stderr line\n"]),
        )
        transport = AsyncStdioTransport()
        transport._process = process
        transport._stderr_task = asyncio.create_task(transport._drain_stderr(process.stderr))

        await transport.close()

        assert process.stdin is not None and process.stdin.closed is True
        assert process.terminated is True
        assert process.wait_calls >= 1
        assert transport._stderr_lines == ["stderr line"]

    asyncio.run(scenario())


def test_stdio_transport_close_surfaces_overlong_stderr_line() -> None:
    async def scenario() -> None:
        stderr = _FakeStreamReader([])
        stderr.raise_on_readline = ValueError("Separator is found, but chunk is longer than limit")
        process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=_FakeStreamReader([]),
            stderr=stderr,
        )
        transport = AsyncStdioTransport()
        transport._process = process
        transport._stderr_task = asyncio.create_task(transport._drain_stderr(process.stderr))

        with pytest.raises(
            AppServerProtocolError,
            match=r"stderr line exceeded configured limit of 4194304 bytes",
        ):
            await transport.close()

    asyncio.run(scenario())


def test_stdio_transport_close_kills_after_wait_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_wait_for(awaitable: object, timeout: float) -> object:
        _ = timeout
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError()

    monkeypatch.setattr("codex.app_server.transports.asyncio.wait_for", fake_wait_for)

    async def scenario() -> None:
        process = _FakeProcess(
            stdin=_FakeStreamWriter(),
            stdout=_FakeStreamReader([]),
            stderr=_FakeStreamReader([]),
            returncode=None,
        )
        transport = AsyncStdioTransport()
        transport._process = process
        transport._stderr_task = asyncio.create_task(transport._drain_stderr(process.stderr))

        await transport.close()

        assert process.terminated is True
        assert process.killed is True

    asyncio.run(scenario())


def test_websocket_transport_start_raises_when_websockets_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "websockets", raising=False)
    original_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "websockets":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        with pytest.raises(
            AppServerConnectionError,
            match=r"install codex-python\[websocket\]",
        ):
            await transport.start()

    asyncio.run(scenario())


def test_websocket_transport_start_raises_on_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeWebsocketsModule:
        exceptions = _FakeWebSocketExceptions

        @staticmethod
        async def connect(url: str) -> _FakeWebSocketConnection:
            _ = url
            raise RuntimeError("connect boom")

    monkeypatch.setitem(sys.modules, "websockets", _FakeWebsocketsModule())

    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        with pytest.raises(AppServerConnectionError, match="Failed to connect"):
            await transport.start()

    asyncio.run(scenario())


def test_websocket_transport_send_receive_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _FakeWebSocketConnection([_json_message := '{"method":"ping","params":{}}'])

    class _FakeWebsocketsModule:
        exceptions = _FakeWebSocketExceptions

        @staticmethod
        async def connect(url: str) -> _FakeWebSocketConnection:
            assert url == "ws://127.0.0.1:4500"
            return connection

    monkeypatch.setitem(sys.modules, "websockets", _FakeWebsocketsModule())

    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        await transport.start()
        await transport.send({"method": "initialize", "params": {}})
        message = await transport.receive()
        await transport.close()

        assert connection.sent == ['{"method":"initialize","params":{}}']
        assert message == {"method": "ping", "params": {}}
        assert connection.closed is True

    asyncio.run(scenario())


def test_websocket_transport_start_passes_explicit_auth_and_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    connection = _FakeWebSocketConnection()

    class _FakeWebsocketsModule:
        exceptions = _FakeWebSocketExceptions

        @staticmethod
        async def connect(url: str, **kwargs: object) -> _FakeWebSocketConnection:
            captured["url"] = url
            captured["kwargs"] = kwargs
            return connection

    monkeypatch.setitem(sys.modules, "websockets", _FakeWebsocketsModule())

    async def scenario() -> None:
        transport = AsyncWebSocketTransport(
            "ws://127.0.0.1:4500",
            AppServerWebSocketOptions(
                bearer_token="secret-token",
                headers={"X-Client": "pytest"},
                subprotocols=("codex-rpc",),
                open_timeout=5.0,
                close_timeout=2.0,
            ),
        )
        await transport.start()
        await transport.close()

    asyncio.run(scenario())

    assert captured["url"] == "ws://127.0.0.1:4500"
    assert captured["kwargs"] == {
        "additional_headers": {
            "Authorization": "Bearer secret-token",
            "X-Client": "pytest",
        },
        "subprotocols": ["codex-rpc"],
        "open_timeout": 5.0,
        "close_timeout": 2.0,
    }


def test_websocket_options_reject_authorization_header() -> None:
    options = AppServerWebSocketOptions(headers={"Authorization": "Basic abc123"})

    with pytest.raises(ValueError, match="headers cannot include Authorization"):
        options.to_connect_kwargs()


def test_websocket_transport_start_preserves_option_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeWebsocketsModule:
        exceptions = _FakeWebSocketExceptions

        @staticmethod
        async def connect(url: str, **kwargs: object) -> _FakeWebSocketConnection:
            _ = (url, kwargs)
            raise AssertionError("connect should not be called when option validation fails")

    monkeypatch.setitem(sys.modules, "websockets", _FakeWebsocketsModule())

    async def scenario() -> None:
        transport = AsyncWebSocketTransport(
            "ws://127.0.0.1:4500",
            AppServerWebSocketOptions(headers={"Authorization": "Basic abc123"}),
        )
        with pytest.raises(ValueError, match="headers cannot include Authorization"):
            await transport.start()

    asyncio.run(scenario())


def test_websocket_transport_receive_returns_none_on_clean_close() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        transport._connection = _FakeWebSocketConnection([_FakeConnectionClosedOK("closed")])
        transport._connection_closed_ok_types = (_FakeConnectionClosedOK,)
        assert await transport.receive() is None

    asyncio.run(scenario())


def test_websocket_transport_receive_raises_on_connection_error() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        transport._connection = _FakeWebSocketConnection([_FakeConnectionClosedError("boom")])
        transport._connection_closed_error_types = (_FakeConnectionClosedError,)
        with pytest.raises(AppServerConnectionError, match="websocket receive failed: boom"):
            await transport.receive()

    asyncio.run(scenario())


def test_websocket_transport_receive_raises_for_non_text_frames() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        transport._connection = _FakeWebSocketConnection([b"binary-frame"])
        with pytest.raises(AppServerProtocolError, match="Expected websocket text frame"):
            await transport.receive()

    asyncio.run(scenario())


def test_websocket_transport_receive_raises_for_invalid_json() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        transport._connection = _FakeWebSocketConnection(["not-json"])
        with pytest.raises(AppServerProtocolError, match="Failed to decode app-server websocket"):
            await transport.receive()

    asyncio.run(scenario())


def test_websocket_transport_receive_raises_for_non_object_payload() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        transport._connection = _FakeWebSocketConnection(['["oops"]'])
        with pytest.raises(AppServerProtocolError, match="Expected app-server message object"):
            await transport.receive()

    asyncio.run(scenario())


def test_websocket_transport_send_raises_when_not_connected() -> None:
    async def scenario() -> None:
        transport = AsyncWebSocketTransport("ws://127.0.0.1:4500")
        with pytest.raises(AppServerClosedError, match="is not connected"):
            await transport.send({"method": "ping"})

    asyncio.run(scenario())
