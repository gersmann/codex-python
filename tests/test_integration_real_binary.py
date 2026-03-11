from __future__ import annotations

import os
from pathlib import Path

import pytest

from codex import Codex, CodexOptions, ThreadStartOptions, TurnOptions
from codex.protocol import types as protocol


def test_run_with_real_codex_binary_and_api_key(tmp_path: Path) -> None:
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

    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": ["OK"]}},
        "required": ["answer"],
        "additionalProperties": False,
    }

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
