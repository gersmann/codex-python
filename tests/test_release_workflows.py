from __future__ import annotations

import os
import subprocess
import textwrap
import tomllib
from pathlib import Path

import pytest


def _runtime_pin() -> str:
    dependencies = tomllib.loads(Path("pyproject.toml").read_text())["project"]["dependencies"]
    pins = [dep for dep in dependencies if dep.startswith("openai-codex-cli-bin==")]
    assert len(pins) == 1
    return pins[0].removeprefix("openai-codex-cli-bin==")


def test_autoreview_installs_the_pinned_codex_runtime() -> None:
    workflow = Path(".github/workflows/codex-autoreview.yml").read_text()

    assert workflow.count(f'pip install "openai-codex-cli-bin=={_runtime_pin()}"') == 2
    assert workflow.index("Install Codex runtime") < workflow.index(
        "gersmann/codex-review-action@v1"
    )


def test_workflows_no_longer_bundle_codex_binaries() -> None:
    for workflow_path in Path(".github/workflows").glob("*.yml"):
        workflow = workflow_path.read_text()

        for retired in (
            "fetch_codex_binary",
            "codex/vendor",
            "maturin",
            "CODEX_BINARY_RELEASE_TAG",
        ):
            assert retired not in workflow, f"{workflow_path} still uses {retired}"


def test_release_workflow_builds_one_pure_python_wheel() -> None:
    workflow = Path(".github/workflows/release-published.yml").read_text()

    assert "run: uv build" in workflow
    assert "-py3-none-any.whl" in workflow
    assert "needs: [prepare, build]" in workflow
    assert workflow.index("Verify Codex runtime pin is published") < workflow.index("run: uv build")


def test_release_workflow_rejects_pypi_oversized_files_before_publish() -> None:
    workflow = Path(".github/workflows/release-published.yml").read_text()

    assert "Verify PyPI file size limit" in workflow
    assert "100 * 1024 * 1024" in workflow
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
    path = repo / "codex/__init__.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("1.2.2" if version_changed else "1.2.3")
    git("add", ".", cwd=repo)
    git("commit", "-m", "Initial version", cwd=repo)
    original_sha = git("rev-parse", "HEAD", cwd=repo)
    git("remote", "add", "origin", str(origin), cwd=repo)
    git("tag", "next", cwd=repo)
    git("push", "origin", "main", "next", cwd=repo)

    if version_changed:
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
    assert workflow.count("ref: ${{ needs.prepare.outputs.build_sha }}") == 1
    assert "BUILD_SHA: ${{ steps.build_sha.outputs.sha }}" in step(
        "Create new semver tag and repoint release"
    )
    assert workflow.index("Resolve build SHA") < workflow.index(
        "Create new semver tag and repoint release"
    )
    # Explicit releases retain their existing tags.
    for name in ("Create new semver tag and repoint release", "Update GitHub Release to new tag"):
        assert "if: ${{ steps.resolve.outputs.mode == 'bump' }}" in step(name)
