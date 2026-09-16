from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

PINNED_CODEX_BINARY_RELEASE_TAG = "rust-v0.153.4"


def test_binary_fetch_workflows_default_to_pinned_codex_release() -> None:
    for workflow_path in (
        Path(".github/workflows/ci.yml"),
        Path(".github/workflows/release-published.yml"),
        Path(".github/workflows/codex-autoreview.yml"),
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

    assert "Compress Windows x64 app-server binary" in workflow
    assert '$version = "5.2.0"' in workflow
    assert "github.com/upx/upx/releases/download/v$version/upx-$version-win64.zip" in workflow
    assert "zipfile.ZIP_BZIP2" not in workflow
    assert "Verify PyPI file size limit" in workflow
    assert "100 * 1024 * 1024" in workflow
    assert "pypa/gh-action-pypi-publish" in workflow
    assert workflow.index("Compress Windows x64 app-server binary") < workflow.index(
        "Build Windows wheel"
    )
    assert workflow.index("Verify PyPI file size limit") < workflow.index(
        "pypa/gh-action-pypi-publish"
    )


@pytest.mark.parametrize("version_changed", [False, True])
def test_next_release_uses_selected_commit_after_branch_advances(
    tmp_path: Path, version_changed: bool
) -> None:
    workflow = Path(".github/workflows/release-published.yml").read_text()

    def step(name: str) -> str:
        return workflow.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]

    def run_step(name: str, env: dict[str, str]) -> None:
        script = textwrap.dedent(step(name).split("        run: |\n", 1)[1])
        script = script.replace("${{ steps.resolve.outputs.version }}", "1.2.3")
        script = script.replace("${{ github.event.repository.default_branch }}", "main")
        subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script],
            cwd=repo,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        ).stdout.strip()

    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    git("init", "--bare", str(origin), cwd=tmp_path)
    git("init", "--initial-branch=main", str(repo), cwd=tmp_path)
    git("config", "user.name", "Release test", cwd=repo)
    git("config", "user.email", "release@example.invalid", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    git("config", "tag.gpgsign", "false", cwd=repo)
    for relative in ("crates/codex_native/Cargo.toml", "codex/__init__.py"):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("1.2.2" if version_changed else "1.2.3")
    git("add", ".", cwd=repo)
    git("commit", "-m", "Initial version", cwd=repo)
    original_sha = git("rev-parse", "HEAD", cwd=repo)
    git("remote", "add", "origin", str(origin), cwd=repo)
    git("tag", "next", cwd=repo)
    git("push", "origin", "main", "next", cwd=repo)

    if version_changed:
        (repo / "crates/codex_native/Cargo.toml").write_text("1.2.3")
        (repo / "codex/__init__.py").write_text("1.2.3")
    output = tmp_path / "output"
    env = dict(os.environ, GITHUB_OUTPUT=str(output), GITHUB_ENV=str(tmp_path / "env"))
    run_step("Commit version bump", env)
    run_step("Resolve build SHA", env)
    build_sha = output.read_text().removeprefix("sha=").strip()
    assert (build_sha != original_sha) == version_changed

    # Another push after source selection must not change the tag's source.
    other = tmp_path / "other"
    git("clone", "--branch", "main", str(origin), str(other), cwd=tmp_path)
    git(
        "-c",
        "user.name=Other",
        "-c",
        "user.email=other@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-m",
        "Branch advances",
        cwd=other,
    )
    git("push", "origin", "main", cwd=other)
    env.update(PLACEHOLDER_TAG="next", VERSION="1.2.3", BUILD_SHA=build_sha)
    run_step("Create new semver tag and repoint release", env)

    assert git("rev-parse", "refs/tags/v1.2.3^{commit}", cwd=origin) == build_sha
    assert git("rev-parse", "refs/heads/main", cwd=origin) != build_sha
    assert workflow.count("ref: ${{ needs.prepare.outputs.build_sha }}") == 2
    assert "BUILD_SHA: ${{ steps.build_sha.outputs.sha }}" in step(
        "Create new semver tag and repoint release"
    )
    assert workflow.index("Resolve build SHA") < workflow.index(
        "Create new semver tag and repoint release"
    )
    # Explicit releases retain their existing tags.
    for name in ("Create new semver tag and repoint release", "Update GitHub Release to new tag"):
        assert "if: ${{ steps.resolve.outputs.mode == 'bump' }}" in step(name)


def test_autoreview_workflow_fetches_codex_binary_before_action() -> None:
    workflow = Path(".github/workflows/codex-autoreview.yml").read_text()

    assert workflow.count("Fetch bundled codex binary") == 2
    assert workflow.count("--target-triple x86_64-unknown-linux-musl") == 2
    assert (
        workflow.count(
            "test -x codex/vendor/x86_64-unknown-linux-musl/codex-app-server/codex-app-server"
        )
        == 2
    )
    assert workflow.index("Fetch bundled codex binary") < workflow.index(
        "gersmann/codex-review-action@v1"
    )
