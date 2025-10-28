from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from codex._binary import bundled_codex_path
from codex.errors import CodexExecError
from codex.options import SandboxMode

INTERNAL_ORIGINATOR_ENV = "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
PYTHON_SDK_ORIGINATOR = "codex_sdk_py"


@dataclass(slots=True, frozen=True)
class CodexExecArgs:
    input: str
    base_url: str | None = None
    api_key: str | None = None
    thread_id: str | None = None
    images: list[str] | None = None
    model: str | None = None
    sandbox_mode: SandboxMode | None = None
    working_directory: str | None = None
    skip_git_repo_check: bool = False
    output_schema_file: str | None = None


class CodexExec:
    def __init__(self, executable_path: str | None = None) -> None:
        if executable_path is not None:
            path = Path(executable_path)
        else:
            try:
                path = bundled_codex_path()
            except CodexExecError as bundled_error:
                system_codex = shutil.which("codex")
                if system_codex is None:
                    raise CodexExecError(
                        f"{bundled_error} Also failed to find `codex` on PATH."
                    ) from bundled_error
                path = Path(system_codex)
        self.executable_path = str(path)

    def run(self, args: CodexExecArgs) -> Iterator[str]:
        command_args: list[str] = ["exec", "--experimental-json"]

        if args.model is not None:
            command_args.extend(["--model", args.model])
        if args.sandbox_mode is not None:
            command_args.extend(["--sandbox", args.sandbox_mode])
        if args.working_directory is not None:
            command_args.extend(["--cd", args.working_directory])
        if args.skip_git_repo_check:
            command_args.append("--skip-git-repo-check")
        if args.output_schema_file is not None:
            command_args.extend(["--output-schema", args.output_schema_file])
        if args.images is not None:
            for image in args.images:
                command_args.extend(["--image", image])
        if args.thread_id:
            command_args.extend(["resume", args.thread_id])

        env = os.environ.copy()
        if INTERNAL_ORIGINATOR_ENV not in env:
            env[INTERNAL_ORIGINATOR_ENV] = PYTHON_SDK_ORIGINATOR
        if args.base_url is not None:
            env["OPENAI_BASE_URL"] = args.base_url
        if args.api_key is not None:
            env["CODEX_API_KEY"] = args.api_key

        try:
            child = subprocess.Popen(
                [self.executable_path, *command_args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env=env,
            )
        except OSError as exc:
            raise CodexExecError(
                f"Failed to spawn codex executable at '{self.executable_path}': {exc}"
            ) from exc

        if child.stdin is None:
            child.kill()
            raise CodexExecError("Child process has no stdin")
        if child.stdout is None:
            child.kill()
            raise CodexExecError("Child process has no stdout")
        if child.stderr is None:
            child.kill()
            raise CodexExecError("Child process has no stderr")

        try:
            child.stdin.write(args.input)
            child.stdin.close()
        except OSError as exc:
            child.kill()
            raise CodexExecError(f"Failed to write input to codex process: {exc}") from exc

        try:
            for line in child.stdout:
                yield line.rstrip("\r\n")
        finally:
            child.stdout.close()

        exit_code = child.wait()
        stderr = child.stderr.read()
        child.stderr.close()

        if exit_code != 0:
            raise CodexExecError(f"Codex exec exited with code {exit_code}: {stderr}")
