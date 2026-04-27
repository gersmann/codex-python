from __future__ import annotations

from pathlib import Path

PINNED_CODEX_BINARY_RELEASE_TAG = "rust-v0.122.0"


def test_binary_fetch_workflows_default_to_pinned_codex_release() -> None:
    for workflow_path in (
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/release-published.yml"),
    ):
        workflow = workflow_path.read_text()

        assert f"vars.CODEX_BINARY_RELEASE_TAG || '{PINNED_CODEX_BINARY_RELEASE_TAG}'" in workflow
        assert "vars.CODEX_BINARY_RELEASE_TAG || 'latest'" not in workflow
