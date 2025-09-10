from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass


class CodexError(Exception):
    """Base exception for codex-python."""


class CodexNotFoundError(CodexError):
    """Raised when the 'codex' binary cannot be found or executed."""

    def __init__(self, executable: str = "codex") -> None:
        super().__init__(
            f"Codex CLI not found: '{executable}'.\n"
            "Install from https://github.com/openai/codex or ensure it is on PATH."
        )
        self.executable = executable


@dataclass(slots=True)
class CodexProcessError(CodexError):
    """Raised when the codex process exits with a non‑zero status."""

    returncode: int
    cmd: Sequence[str]
    stdout: str
    stderr: str

    def __str__(self) -> str:  # pragma: no cover - repr is sufficient
        return (
            f"Codex process failed with exit code {self.returncode}.\n"
            f"Command: {' '.join(self.cmd)}\n"
            f"stderr:\n{self.stderr.strip()}"
        )


def find_binary(executable: str = "codex") -> str:
    """Return the absolute path to the Codex CLI binary or raise if not found."""
    path = shutil.which(executable)
    if not path:
        raise CodexNotFoundError(executable)
    return path


def run_exec(
    prompt: str,
    *,
    model: str | None = None,
    oss: bool = False,
    full_auto: bool = False,
    cd: str | None = None,
    skip_git_repo_check: bool = False,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
    executable: str = "codex",
    extra_args: Iterable[str] | None = None,
    json: bool = False,
) -> str:
    """
    Run `codex exec` with the given prompt and return stdout as text.

    - Raises CodexNotFoundError if the binary is unavailable.
    - Raises CodexProcessError on non‑zero exit with captured stdout/stderr.
    """
    bin_path = find_binary(executable)

    cmd: list[str] = [bin_path]

    if cd:
        cmd.extend(["--cd", cd])
    if model:
        cmd.extend(["-m", model])
    if oss:
        cmd.append("--oss")
    if full_auto:
        cmd.append("--full-auto")
    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if extra_args:
        cmd.extend(list(extra_args))

    cmd.append("exec")
    if json:
        cmd.append("--json")
    cmd.append(prompt)

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(dict(env) if env else {})},
        check=False,
    )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0:
        raise CodexProcessError(
            returncode=completed.returncode,
            cmd=tuple(cmd),
            stdout=stdout,
            stderr=stderr,
        )
    return stdout


@dataclass(slots=True)
class CodexClient:
    """Lightweight, synchronous client for the Codex CLI.

    Provides defaults for repeated invocations and convenience helpers.
    """

    executable: str = "codex"
    model: str | None = None
    full_auto: bool = False
    cd: str | None = None
    env: Mapping[str, str] | None = None
    extra_args: Sequence[str] | None = None

    def ensure_available(self) -> str:
        """Return the resolved binary path or raise CodexNotFoundError."""
        return find_binary(self.executable)

    def run(
        self,
        prompt: str,
        *,
        model: str | None = None,
        oss: bool | None = None,
        full_auto: bool | None = None,
        cd: str | None = None,
        skip_git_repo_check: bool | None = None,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
        extra_args: Iterable[str] | None = None,
    ) -> str:
        """Execute `codex exec` and return stdout.

        Explicit arguments override the client's defaults.
        """
        eff_model = model if model is not None else self.model
        eff_full_auto = full_auto if full_auto is not None else self.full_auto
        eff_cd = cd if cd is not None else self.cd
        eff_oss = bool(oss) if oss is not None else False
        eff_skip_git = bool(skip_git_repo_check) if skip_git_repo_check is not None else False

        # Merge environment overlays; run_exec will merge with os.environ
        merged_env: Mapping[str, str] | None
        if self.env and env:
            tmp = dict(self.env)
            tmp.update(env)
            merged_env = tmp
        else:
            merged_env = env or self.env

        # Compose extra args
        eff_extra: list[str] = []
        if self.extra_args:
            eff_extra.extend(self.extra_args)
        if extra_args:
            eff_extra.extend(list(extra_args))

        return run_exec(
            prompt,
            model=eff_model,
            oss=eff_oss,
            full_auto=eff_full_auto,
            cd=eff_cd,
            skip_git_repo_check=eff_skip_git,
            timeout=timeout,
            env=merged_env,
            executable=self.executable,
            extra_args=eff_extra,
        )
