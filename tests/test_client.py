import os
import stat
from pathlib import Path

import pytest

from codex import CodexClient, CodexNotFoundError


def test_client_missing_binary():
    client = CodexClient(executable="codex-does-not-exist-xyz")
    with pytest.raises(CodexNotFoundError):
        client.ensure_available()
    with pytest.raises(CodexNotFoundError):
        client.run("hello")


def test_client_runs_with_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Dummy codex that echoes args and succeeds
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex_path = bin_dir / "codex"
    codex_path.write_text("""#!/bin/sh\necho \"[dummy] $@\"\n""")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}" + os.environ.get("PATH", ""))

    client = CodexClient(model="test-model", full_auto=True, extra_args=["--ask-for-approval"])
    out = client.run("hello world")

    # Ensure key flags and prompt are passed along; order-insensitive
    assert "[dummy]" in out
    assert "exec" in out
    assert "hello world" in out
    assert "--full-auto" in out
    assert "-m test-model" in out
    assert "--ask-for-approval" in out
