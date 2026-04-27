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


def test_release_workflow_builds_split_macos_wheels() -> None:
    workflow = Path(".github/workflows/release-published.yml").read_text()

    assert "macos-aarch64" in workflow
    assert "macos-x86_64" in workflow
    assert "codex-targets: aarch64-apple-darwin" in workflow
    assert "codex-targets: x86_64-apple-darwin" in workflow
    assert "os: macos-15-intel" in workflow
    assert "os: macos-13" not in workflow
    assert "macos-universal2" not in workflow
    assert "universal2-apple-darwin" not in workflow


def test_release_workflow_rejects_pypi_oversized_files_before_publish() -> None:
    workflow = Path(".github/workflows/release-published.yml").read_text()

    assert "Verify PyPI file size limit" in workflow
    assert "100 * 1024 * 1024" in workflow
    assert "pypa/gh-action-pypi-publish" in workflow
    assert workflow.index("Verify PyPI file size limit") < workflow.index(
        "pypa/gh-action-pypi-publish"
    )
