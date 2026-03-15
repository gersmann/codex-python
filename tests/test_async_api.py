from __future__ import annotations

from typing import Any

import pytest

from codex import Codex, CodexOptions
from codex.app_server import AppServerClient, AppServerProcessOptions
from codex.errors import CodexError


class _FakeThread:
    def __init__(self, thread_id: str) -> None:
        self.id = thread_id
        self.run_calls: list[tuple[object, object | None]] = []

    def run(self, input: object, options: object | None = None) -> object:
        self.run_calls.append((input, options))
        raise AssertionError("streaming is covered in test_api_features")


class _FakeAccountClient:
    def __init__(self) -> None:
        self.login_api_key_calls: list[str] = []

    def login_api_key(self, *, api_key: str) -> object:
        self.login_api_key_calls.append(api_key)
        return object()


class _FakeClient:
    def __init__(self) -> None:
        self.start_calls: list[object | None] = []
        self.resume_calls: list[tuple[str, object | None]] = []
        self.closed = False
        self.account = _FakeAccountClient()

    def start_thread(
        self, options: object | None = None, *, tools: object | None = None
    ) -> _FakeThread:
        _ = tools
        self.start_calls.append(options)
        return _FakeThread("thr-1")

    def resume_thread(self, thread_id: str, options: object | None = None) -> _FakeThread:
        self.resume_calls.append((thread_id, options))
        return _FakeThread(thread_id)

    def close(self) -> None:
        self.closed = True


def _patch_connect_stdio(
    monkeypatch: pytest.MonkeyPatch,
    fake_client: _FakeClient,
    capture: dict[str, Any],
) -> None:
    def fake_connect_stdio(
        cls: type[AppServerClient],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeClient:
        _ = cls
        capture.setdefault("calls", 0)
        capture["calls"] += 1
        capture["process_options"] = process_options
        capture["initialize_options"] = initialize_options
        return fake_client

    monkeypatch.setattr(AppServerClient, "connect_stdio", classmethod(fake_connect_stdio))


def test_codex_start_and_resume_thread_materialize_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeClient()
    capture: dict[str, Any] = {}
    _patch_connect_stdio(monkeypatch, fake_client, capture)

    client = Codex()

    assert capture == {}

    thread = client.start_thread()
    assert thread.id == "thr-1"
    assert capture["calls"] == 1

    resumed = client.resume_thread("thread-1")
    assert resumed.id == "thread-1"
    assert capture["calls"] == 1
    assert len(fake_client.start_calls) == 1
    assert fake_client.start_calls[0] is not None
    assert len(fake_client.resume_calls) == 1
    assert fake_client.resume_calls[0][0] == "thread-1"
    assert fake_client.resume_calls[0][1] is not None


def test_codex_reuses_one_private_app_server_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    capture: dict[str, Any] = {}
    _patch_connect_stdio(monkeypatch, fake_client, capture)

    client = Codex(CodexOptions(codex_path_override="/tmp/codex", api_key="key"))

    first = client._ensure_client()
    second = client._ensure_client()

    assert first is fake_client
    assert second is fake_client
    assert capture["calls"] == 1
    assert capture["process_options"] == AppServerProcessOptions(
        codex_path_override="/tmp/codex",
        api_key="key",
    )
    assert fake_client.account.login_api_key_calls == ["key"]


def test_codex_close_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    _patch_connect_stdio(monkeypatch, fake_client, {})

    client = Codex()
    _ = client._ensure_client()

    client.close()
    client.close()

    assert fake_client.closed is True


def test_codex_context_manager_closes_private_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    _patch_connect_stdio(monkeypatch, fake_client, {})

    with Codex() as client:
        _ = client._ensure_client()

    assert fake_client.closed is True


def test_codex_rejects_new_threads_after_close(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient()
    _patch_connect_stdio(monkeypatch, fake_client, {})

    client = Codex()
    client.close()

    with pytest.raises(CodexError, match="closed"):
        client.start_thread()

    with pytest.raises(CodexError, match="closed"):
        client.resume_thread("thread-1")
