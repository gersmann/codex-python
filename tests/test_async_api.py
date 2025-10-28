from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

import codex.exec as codex_exec_module
from codex.errors import CodexExecError
from codex.exec import CodexExec, CodexExecArgs


class _FakeStdin:
    def __init__(self) -> None:
        self.buffer = ""
        self.closed = False

    def write(self, value: str) -> int:
        self.buffer += value
        return len(value)

    def close(self) -> None:
        self.closed = True


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.closed = False

    def __iter__(self) -> _FakeStdout:
        return self

    def __next__(self) -> str:
        if not self._lines:
            raise StopIteration
        return self._lines.pop(0)

    def close(self) -> None:
        self.closed = True


class _FakeStderr:
    def __init__(self, content: str) -> None:
        self._content = content
        self.closed = False

    def read(self) -> str:
        return self._content

    def close(self) -> None:
        self.closed = True


@dataclass
class _FakeProcess:
    stdin: _FakeStdin
    stdout: _FakeStdout
    stderr: _FakeStderr
    exit_code: int
    killed: bool = False

    def wait(self) -> int:
        return self.exit_code

    def kill(self) -> None:
        self.killed = True


def test_exec_builds_command_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout(["line-1\n", "line-2\r\n"]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )

    def fake_popen(
        cmd: list[str],
        stdin: int,
        stdout: int,
        stderr: int,
        text: bool,
        encoding: str,
        env: dict[str, str],
    ) -> _FakeProcess:
        captured["cmd"] = cmd
        captured["stdin"] = stdin
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["text"] = text
        captured["encoding"] = encoding
        captured["env"] = env
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.delenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", raising=False)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    lines = list(
        exec_runner.run(
            CodexExecArgs(
                input="Hello",
                base_url="http://localhost:8080",
                api_key="test-key",
                thread_id="thread-1",
                images=["/tmp/1.png", "/tmp/2.png"],
                model="gpt-test-1",
                sandbox_mode="workspace-write",
                working_directory="/tmp/work",
                skip_git_repo_check=True,
                output_schema_file="/tmp/schema.json",
            )
        )
    )

    assert lines == ["line-1", "line-2"]
    assert fake_process.stdin.buffer == "Hello"
    assert fake_process.stdin.closed is True

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "/tmp/codex"
    assert cmd[1:] == [
        "exec",
        "--experimental-json",
        "--model",
        "gpt-test-1",
        "--sandbox",
        "workspace-write",
        "--cd",
        "/tmp/work",
        "--skip-git-repo-check",
        "--output-schema",
        "/tmp/schema.json",
        "--image",
        "/tmp/1.png",
        "--image",
        "/tmp/2.png",
        "resume",
        "thread-1",
    ]

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "codex_sdk_py"
    assert env["OPENAI_BASE_URL"] == "http://localhost:8080"
    assert env["CODEX_API_KEY"] == "test-key"


def test_exec_preserves_preexisting_originator(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    captured_env: dict[str, str] = {}

    def fake_popen(**kwargs: object) -> _FakeProcess:
        env = kwargs.get("env")
        assert isinstance(env, dict)
        captured_env.update(env)
        return fake_process

    def popen_adapter(
        cmd: list[str],
        stdin: int,
        stdout: int,
        stderr: int,
        text: bool,
        encoding: str,
        env: dict[str, str],
    ) -> _FakeProcess:
        _ = (cmd, stdin, stdout, stderr, text, encoding)
        return fake_popen(env=env)

    monkeypatch.setattr(subprocess, "Popen", popen_adapter)
    monkeypatch.setenv("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "pre-set")

    exec_runner = CodexExec(executable_path="/tmp/codex")
    list(exec_runner.run(CodexExecArgs(input="Hello")))

    assert captured_env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "pre-set"


def test_exec_raises_on_non_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr("boom"),
        exit_code=42,
    )

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: fake_process,
    )

    exec_runner = CodexExec(executable_path="/tmp/codex")
    with pytest.raises(CodexExecError, match="exited with code 42"):
        list(exec_runner.run(CodexExecArgs(input="Hello")))


def test_exec_raises_when_spawn_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_oserror(*args: object, **kwargs: object) -> object:
        _ = (args, kwargs)
        raise OSError("nope")

    monkeypatch.setattr(subprocess, "Popen", raise_oserror)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    with pytest.raises(CodexExecError, match="Failed to spawn codex executable"):
        list(exec_runner.run(CodexExecArgs(input="Hello")))


def test_exec_falls_back_to_path_codex_when_bundled_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codex_exec_module,
        "bundled_codex_path",
        lambda: (_ for _ in ()).throw(CodexExecError("Bundled codex binary not found")),
    )
    monkeypatch.setattr(codex_exec_module.shutil, "which", lambda _: "/usr/bin/codex")

    exec_runner = CodexExec()
    assert exec_runner.executable_path == "/usr/bin/codex"


def test_exec_raises_when_bundled_missing_and_no_path_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        codex_exec_module,
        "bundled_codex_path",
        lambda: (_ for _ in ()).throw(CodexExecError("Bundled codex binary not found")),
    )
    monkeypatch.setattr(codex_exec_module.shutil, "which", lambda _: None)

    with pytest.raises(CodexExecError, match="failed to find `codex` on PATH"):
        CodexExec()
