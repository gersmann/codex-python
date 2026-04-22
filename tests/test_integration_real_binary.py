from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path

import pytest

from codex import Codex, CodexOptions, ThreadStartOptions, TurnOptions
from codex.app_server import AsyncAppServerClient
from codex.app_server.options import AppServerProcessOptions
from codex.protocol import types as protocol

_COMMAND_OUTPUT_UNDER_TEST = "codex-python-integration-output"


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


def test_streamed_command_exec_events_with_real_codex_binary(tmp_path: Path) -> None:
    binary, _api_key, child_env = _integration_binary_and_env(tmp_path)

    async def scenario() -> None:
        client = await AsyncAppServerClient.connect_stdio(
            AppServerProcessOptions(
                codex_path_override=str(binary),
                env=child_env,
            )
        )
        try:
            process_id = "codex-python-integration-git-diff"
            subscription = client.events.subscribe({"command/exec/outputDelta"})
            command_task = asyncio.create_task(
                client.command.execute(
                    command=["/bin/sh", "-c", f"printf {_COMMAND_OUTPUT_UNDER_TEST}"],
                    cwd=str(tmp_path),
                    process_id=process_id,
                    stream_stdout_stderr=True,
                    timeout_ms=5000,
                )
            )

            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            observed_events: list[str] = []

            while True:
                try:
                    event = await asyncio.wait_for(subscription.next(), timeout=0.2)
                except TimeoutError:
                    if command_task.done():
                        break
                    continue

                method = getattr(getattr(event, "method", None), "root", type(event).__name__)
                observed_events.append(f"{method}: {type(event).__name__}")
                if not isinstance(event, protocol.CommandExecOutputDeltaNotificationModel):
                    continue
                if event.params.processId != process_id:
                    continue
                output_chunk = base64.b64decode(event.params.deltaBase64).decode()
                if event.params.stream.root == "stdout":
                    stdout_chunks.append(output_chunk)
                if event.params.stream.root == "stderr":
                    stderr_chunks.append(output_chunk)

            result = await command_task
            await subscription.close()
            event_summary = "\n".join(observed_events)
            streamed_stdout = "".join(stdout_chunks)
            streamed_stderr = "".join(stderr_chunks)
            failure_context = (
                f"result={result!r}\n"
                f"streamed_stdout={streamed_stdout!r}\n"
                f"streamed_stderr={streamed_stderr!r}\n"
                f"{event_summary}"
            )
            assert result.exit_code == 0, failure_context
            assert result.stderr == ""
            assert result.stdout == ""
            assert streamed_stdout == _COMMAND_OUTPUT_UNDER_TEST, failure_context
            assert streamed_stderr == "", failure_context
        finally:
            await client.close()

    asyncio.run(scenario())
