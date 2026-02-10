from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from codex import Codex, CodexOptions, ThreadOptions, TurnOptions


def test_run_with_real_codex_binary_and_api_key() -> None:
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

    client = Codex(CodexOptions(codex_path_override=str(binary), api_key=api_key))
    thread = client.start_thread(
        ThreadOptions(
            model="gpt-5-mini",
            model_reasoning_effort="low",
            web_search_mode="disabled",
            skip_git_repo_check=True,
        )
    )
    result = thread.run(
        'Respond with JSON containing {"answer":"OK"}.',
        TurnOptions(output_schema=schema),
    )

    assert thread.id is not None
    parsed = json.loads(result.final_response)
    assert parsed == {"answer": "OK"}
    assert result.usage is not None
