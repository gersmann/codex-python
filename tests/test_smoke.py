from __future__ import annotations

import codex
from codex import Codex, CodexOptions


def test_basic_import_and_api() -> None:
    assert codex.__version__ == "1.0.0"
    assert Codex is codex.Codex


def test_start_and_resume_thread() -> None:
    client = Codex(CodexOptions(codex_path_override="/tmp/codex"))

    thread = client.start_thread()
    assert thread.id is None

    resumed = client.resume_thread("thread-1")
    assert resumed.id == "thread-1"
