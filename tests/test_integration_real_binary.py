from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from codex import Codex, CodexOptions, ThreadStartOptions, TurnOptions
from codex.protocol import types as protocol

_COMMAND_OUTPUT_UNDER_TEST = "codex-python-command-stream"


def _integration_binary_and_env(tmp_path: Path) -> tuple[Path, str, dict[str, str]]:
    if os.environ.get("CODEX_INTEGRATION_TEST") != "1":
        pytest.skip("integration test disabled; set CODEX_INTEGRATION_TEST=1")

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        pytest.skip("OPENAI_API_KEY is required for integration test")

    binary_path = os.environ.get("CODEX_BINARY_PATH")
    if binary_path is None:
        pytest.skip("CODEX_BINARY_PATH is required for integration test")

    binary = Path(binary_path)
    if not binary.is_file():
        pytest.skip(f"codex binary not found at {binary}")

    isolated_home = tmp_path / "home"
    isolated_config = tmp_path / "xdg-config"
    isolated_data = tmp_path / "xdg-data"
    isolated_state = tmp_path / "xdg-state"
    isolated_home.mkdir()
    isolated_config.mkdir()
    isolated_data.mkdir()
    isolated_state.mkdir()

    child_env = {
        "HOME": str(isolated_home),
        "XDG_CONFIG_HOME": str(isolated_config),
        "XDG_DATA_HOME": str(isolated_data),
        "XDG_STATE_HOME": str(isolated_state),
    }
    for key in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "TMPDIR", "TMP", "TEMP"):
        value = os.environ.get(key)
        if value is not None:
            child_env[key] = value

    return binary, api_key, child_env


def _create_git_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "codex-python-tests@example.com")
    _git(path, "config", "user.name", "Codex Python Tests")

    tracked_file = path / "notes.txt"
    tracked_file.write_text("one\n", encoding="utf-8")
    _git(path, "add", "notes.txt")
    _git(path, "commit", "-m", "initial")
    return path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def test_run_with_real_codex_binary_and_api_key(tmp_path: Path) -> None:
    binary, api_key, child_env = _integration_binary_and_env(tmp_path)

    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": ["OK"]}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    with Codex(
        CodexOptions(
            codex_path_override=str(binary),
            api_key=api_key,
            env=child_env,
        )
    ) as client:
        thread = client.start_thread(
            ThreadStartOptions(
                model="gpt-5-mini",
                config={
                    "skip_git_repo_check": True,
                    "web_search": "disabled",
                },
            )
        )
        result = thread.run_json(
            'Respond with JSON containing {"answer":"OK"}.',
            TurnOptions(output_schema=schema, effort=protocol.ReasoningEffort("low")),
        )

        assert thread.id is not None
        assert result == {"answer": "OK"}


def test_streamed_command_events_with_real_codex_binary(tmp_path: Path) -> None:
    binary, api_key, child_env = _integration_binary_and_env(tmp_path)
    repo = _create_git_repo(tmp_path / "repo")

    with Codex(
        CodexOptions(
            codex_path_override=str(binary),
            api_key=api_key,
            env=child_env,
        )
    ) as client:
        thread = client.start_thread(
            ThreadStartOptions(
                model="gpt-5-mini",
                approval_policy=protocol.AskForApproval("never"),
                cwd=str(repo),
                sandbox=protocol.SandboxMode("workspace-write"),
                config={
                    "skip_git_repo_check": True,
                    "web_search": "disabled",
                },
            )
        )
        stream = thread.run(
            "Run a shell command exactly once to print "
            f"{_COMMAND_OUTPUT_UNDER_TEST!r}. After the command completes, reply OK.",
            TurnOptions(effort=protocol.ReasoningEffort("low")),
        )
        events = list(stream)

        command_started_items = [
            event.params.item.root
            for event in events
            if isinstance(event, protocol.ItemStartedNotificationModel)
            and isinstance(event.params.item.root, protocol.CommandExecutionThreadItem)
        ]
        command_completed_items = [
            event.params.item.root
            for event in events
            if isinstance(event, protocol.ItemCompletedNotificationModel)
            and isinstance(event.params.item.root, protocol.CommandExecutionThreadItem)
        ]
        command_event_context = (
            f"started_commands={[item.command for item in command_started_items]!r}\n"
            f"completed_commands={[(item.command, item.exitCode, item.aggregatedOutput) for item in command_completed_items]!r}\n"
            f"final_text={stream.final_text!r}"
        )
        assert thread.id is not None
        assert any(isinstance(event, protocol.TurnStartedNotificationModel) for event in events)
        assert any(isinstance(event, protocol.TurnCompletedNotificationModel) for event in events)
        assert command_started_items, command_event_context
        assert any(
            item.exitCode == 0
            and item.aggregatedOutput is not None
            and _COMMAND_OUTPUT_UNDER_TEST in item.aggregatedOutput
            for item in command_completed_items
        ), command_event_context
        assert stream.final_turn is not None
        assert stream.final_turn.status.root == "completed"
        assert stream.final_text.strip() == "OK"
