from __future__ import annotations

import re
from typing import Any

import pytest

import codex
from codex import Codex, CodexOptions
from codex.app_server import AppServerClient, AppServerProcessOptions


class _FakeThread:
    def __init__(self, thread_id: str) -> None:
        self.id = thread_id


class _FakeClient:
    def start_thread(self, options: object | None = None) -> _FakeThread:
        _ = options
        return _FakeThread("thr-1")

    def resume_thread(self, thread_id: str, options: object | None = None) -> _FakeThread:
        _ = options
        return _FakeThread(thread_id)

    def close(self) -> None:
        return None


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
        _ = (cls, initialize_options)
        capture["process_options"] = process_options
        return fake_client

    monkeypatch.setattr(AppServerClient, "connect_stdio", classmethod(fake_connect_stdio))


def test_basic_import_and_api() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", codex.__version__) is not None
    assert Codex is codex.Codex


def test_start_and_resume_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _patch_connect_stdio(monkeypatch, _FakeClient(), capture)
    client = Codex(CodexOptions(codex_path_override="/tmp/codex"))

    thread = client.start_thread()
    assert thread.id == "thr-1"

    resumed = client.resume_thread("thread-1")
    assert resumed.id == "thread-1"
    assert capture["process_options"] == AppServerProcessOptions(codex_path_override="/tmp/codex")
