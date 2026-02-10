from __future__ import annotations

import re

import codex
from codex import Codex, CodexOptions


def test_basic_import_and_api() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", codex.__version__) is not None
    assert Codex is codex.Codex


def test_start_and_resume_thread() -> None:
    client = Codex(CodexOptions(codex_path_override="/tmp/codex"))

    thread = client.start_thread()
    assert thread.id is None

    resumed = client.resume_thread("thread-1")
    assert resumed.id == "thread-1"
