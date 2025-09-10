import os
import stat
from pathlib import Path

import pytest

from codex.api import CodexNotFoundError, run_exec


def test_missing_binary_raises():
    with pytest.raises(CodexNotFoundError):
        run_exec("hello", executable="codex-does-not-exist-xyz")


def test_runs_with_dummy_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Create a dummy 'codex' executable that echoes args and succeeds
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex_path = bin_dir / "codex"
    codex_path.write_text("""#!/bin/sh\necho \"[dummy] $@\"\n""")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)

    # Prepend our dummy bin to PATH
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}" + os.environ.get("PATH", ""))

    out = run_exec("hello world", executable="codex")
    assert "[dummy] exec hello world" in out
