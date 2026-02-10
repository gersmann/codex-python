from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, cast

import pytest

import codex.exec as codex_exec_module
from codex.errors import CodexExecError
from codex.exec import CodexExec, CodexExecArgs, serialize_config_overrides


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

    exec_runner = CodexExec(
        executable_path="/tmp/codex",
        config_overrides={
            "approval_policy": "never",
            "sandbox_workspace_write": {"network_access": False},
            "retry_budget": 3,
            "tool_rules": {"allow": ["git status", "git diff"]},
        },
    )
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
                additional_directories=["../backend", "/tmp/shared"],
                skip_git_repo_check=True,
                output_schema_file="/tmp/schema.json",
                model_reasoning_effort="high",
                network_access_enabled=True,
                web_search_mode="cached",
                approval_policy="on-request",
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
        "--config",
        'approval_policy="never"',
        "--config",
        "sandbox_workspace_write.network_access=false",
        "--config",
        "retry_budget=3",
        "--config",
        'tool_rules.allow=["git status", "git diff"]',
        "--model",
        "gpt-test-1",
        "--sandbox",
        "workspace-write",
        "--cd",
        "/tmp/work",
        "--add-dir",
        "../backend",
        "--add-dir",
        "/tmp/shared",
        "--skip-git-repo-check",
        "--output-schema",
        "/tmp/schema.json",
        "--config",
        'model_reasoning_effort="high"',
        "--config",
        "sandbox_workspace_write.network_access=true",
        "--config",
        'web_search="cached"',
        "--config",
        'approval_policy="on-request"',
        "resume",
        "thread-1",
        "--image",
        "/tmp/1.png",
        "--image",
        "/tmp/2.png",
    ]

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "codex_sdk_py"
    assert env["OPENAI_BASE_URL"] == "http://localhost:8080"
    assert env["CODEX_API_KEY"] == "test-key"


def test_exec_resume_args_come_before_image_args(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    captured_cmd: list[str] = []

    def fake_popen(
        cmd: list[str],
        stdin: int,
        stdout: int,
        stderr: int,
        text: bool,
        encoding: str,
        env: dict[str, str],
    ) -> _FakeProcess:
        _ = (stdin, stdout, stderr, text, encoding, env)
        captured_cmd.extend(cmd)
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    list(exec_runner.run(CodexExecArgs(input="Hello", thread_id="thread-id", images=["img.png"])))

    resume_index = captured_cmd.index("resume")
    image_index = captured_cmd.index("--image")
    assert resume_index < image_index


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


def test_exec_env_override_does_not_inherit_parent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    captured_env: dict[str, str] = {}

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
        captured_env.update(env)
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", popen_adapter)
    monkeypatch.setenv("CODEX_ENV_SHOULD_NOT_LEAK", "leak")

    exec_runner = CodexExec(executable_path="/tmp/codex", env_override={"CUSTOM_ENV": "custom"})
    list(
        exec_runner.run(
            CodexExecArgs(input="Hello", base_url="http://localhost:8080", api_key="test-key")
        )
    )

    assert captured_env["CUSTOM_ENV"] == "custom"
    assert "CODEX_ENV_SHOULD_NOT_LEAK" not in captured_env
    assert captured_env["OPENAI_BASE_URL"] == "http://localhost:8080"
    assert captured_env["CODEX_API_KEY"] == "test-key"
    assert captured_env["CODEX_INTERNAL_ORIGINATOR_OVERRIDE"] == "codex_sdk_py"


def test_exec_prefers_web_search_mode_over_legacy_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    captured_cmd: list[str] = []

    def popen_adapter(
        cmd: list[str],
        stdin: int,
        stdout: int,
        stderr: int,
        text: bool,
        encoding: str,
        env: dict[str, str],
    ) -> _FakeProcess:
        _ = (stdin, stdout, stderr, text, encoding, env)
        captured_cmd.extend(cmd)
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", popen_adapter)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    list(
        exec_runner.run(
            CodexExecArgs(
                input="Hello",
                web_search_mode="cached",
                web_search_enabled=False,
            )
        )
    )

    assert "--config" in captured_cmd
    config_values = [
        captured_cmd[i + 1] for i, item in enumerate(captured_cmd) if item == "--config"
    ]
    assert 'web_search="cached"' in config_values
    assert 'web_search="disabled"' not in config_values


def test_exec_uses_legacy_web_search_boolean_when_mode_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout([]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    captured_cmd: list[str] = []

    def popen_adapter(
        cmd: list[str],
        stdin: int,
        stdout: int,
        stderr: int,
        text: bool,
        encoding: str,
        env: dict[str, str],
    ) -> _FakeProcess:
        _ = (stdin, stdout, stderr, text, encoding, env)
        captured_cmd.extend(cmd)
        return fake_process

    monkeypatch.setattr(subprocess, "Popen", popen_adapter)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    list(exec_runner.run(CodexExecArgs(input="Hello", web_search_enabled=False)))

    config_values = [
        captured_cmd[i + 1] for i, item in enumerate(captured_cmd) if item == "--config"
    ]
    assert 'web_search="disabled"' in config_values


def test_serialize_config_overrides_handles_empty_object() -> None:
    assert serialize_config_overrides({}) == []


def test_serialize_config_overrides_rejects_null_values() -> None:
    with pytest.raises(ValueError, match="cannot be null"):
        serialize_config_overrides(
            cast(codex_exec_module.CodexConfigObject, {"approval_policy": None})
        )


def test_serialize_config_overrides_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="finite number"):
        serialize_config_overrides(
            cast(codex_exec_module.CodexConfigObject, {"retry_budget": float("inf")})
        )


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


def test_exec_aborts_before_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    class AbortedSignal:
        def __init__(self) -> None:
            self.aborted = True

    popen_called = False

    def popen_adapter(*args: object, **kwargs: object) -> object:
        nonlocal popen_called
        popen_called = True
        _ = (args, kwargs)
        raise AssertionError("Popen should not be called for pre-aborted signal")

    monkeypatch.setattr(subprocess, "Popen", popen_adapter)

    exec_runner = CodexExec(executable_path="/tmp/codex")
    with pytest.raises(CodexExecError, match="aborted before start"):
        list(exec_runner.run(CodexExecArgs(input="Hello", signal=AbortedSignal())))

    assert popen_called is False


def test_exec_aborts_during_stream_iteration(monkeypatch: pytest.MonkeyPatch) -> None:
    class MutableSignal:
        def __init__(self) -> None:
            self.aborted = False

    fake_process = _FakeProcess(
        stdin=_FakeStdin(),
        stdout=_FakeStdout(["line-1\n", "line-2\n"]),
        stderr=_FakeStderr(""),
        exit_code=0,
    )
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: fake_process)

    signal = MutableSignal()
    exec_runner = CodexExec(executable_path="/tmp/codex")
    stream = exec_runner.run(CodexExecArgs(input="Hello", signal=signal))

    assert next(stream) == "line-1"
    signal.aborted = True

    with pytest.raises(CodexExecError, match="aborted"):
        next(stream)

    assert fake_process.killed is True


def test_exec_rejects_invalid_signal_type() -> None:
    class InvalidSignal:
        pass

    exec_runner = CodexExec(executable_path="/tmp/codex")
    invalid_signal = cast(Any, InvalidSignal())

    with pytest.raises(TypeError, match="signal must expose"):
        list(exec_runner.run(CodexExecArgs(input="Hello", signal=invalid_signal)))


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
