from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from codex._binary import bundled_codex_path
from codex.errors import CodexExecError
from codex.options import (
    ApprovalMode,
    CancelSignal,
    CodexConfigObject,
    CodexConfigValue,
    ModelReasoningEffort,
    SandboxMode,
    SupportsAborted,
    SupportsIsSet,
    WebSearchMode,
)

INTERNAL_ORIGINATOR_ENV = "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
PYTHON_SDK_ORIGINATOR = "codex_sdk_py"
TOML_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


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
    additional_directories: list[str] | None = None
    skip_git_repo_check: bool = False
    output_schema_file: str | None = None
    model_reasoning_effort: ModelReasoningEffort | None = None
    signal: CancelSignal | None = None
    network_access_enabled: bool | None = None
    web_search_mode: WebSearchMode | None = None
    web_search_enabled: bool | None = None
    approval_policy: ApprovalMode | None = None


class CodexExec:
    def __init__(
        self,
        executable_path: str | None = None,
        env_override: dict[str, str] | None = None,
        config_overrides: CodexConfigObject | None = None,
    ) -> None:
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
        self._env_override = env_override
        self._config_overrides = config_overrides

    def run(self, args: CodexExecArgs) -> Iterator[str]:
        if is_signal_aborted(args.signal):
            raise CodexExecError("Codex exec aborted before start")

        command_args: list[str] = ["exec", "--experimental-json"]

        if self._config_overrides is not None:
            for override in serialize_config_overrides(self._config_overrides):
                command_args.extend(["--config", override])

        if args.model is not None:
            command_args.extend(["--model", args.model])
        if args.sandbox_mode is not None:
            command_args.extend(["--sandbox", args.sandbox_mode])
        if args.working_directory is not None:
            command_args.extend(["--cd", args.working_directory])
        if args.additional_directories:
            for directory in args.additional_directories:
                command_args.extend(["--add-dir", directory])
        if args.skip_git_repo_check:
            command_args.append("--skip-git-repo-check")
        if args.output_schema_file is not None:
            command_args.extend(["--output-schema", args.output_schema_file])
        if args.model_reasoning_effort is not None:
            command_args.extend(
                [
                    "--config",
                    f'model_reasoning_effort="{args.model_reasoning_effort}"',
                ]
            )
        if args.network_access_enabled is not None:
            command_args.extend(
                [
                    "--config",
                    (
                        "sandbox_workspace_write.network_access="
                        f"{format_toml_bool(args.network_access_enabled)}"
                    ),
                ]
            )
        if args.web_search_mode is not None:
            command_args.extend(["--config", f'web_search="{args.web_search_mode}"'])
        elif args.web_search_enabled is True:
            command_args.extend(["--config", 'web_search="live"'])
        elif args.web_search_enabled is False:
            command_args.extend(["--config", 'web_search="disabled"'])
        if args.approval_policy is not None:
            command_args.extend(["--config", f'approval_policy="{args.approval_policy}"'])
        if args.thread_id is not None:
            command_args.extend(["resume", args.thread_id])
        if args.images is not None:
            for image in args.images:
                command_args.extend(["--image", image])

        env = self.build_env(base_url=args.base_url, api_key=args.api_key)

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
            terminate_child(child)
            raise CodexExecError("Child process has no stdin")
        if child.stdout is None:
            terminate_child(child)
            raise CodexExecError("Child process has no stdout")
        if child.stderr is None:
            terminate_child(child)
            raise CodexExecError("Child process has no stderr")

        if is_signal_aborted(args.signal):
            terminate_child(child)
            _ = child.stderr.read()
            child.stderr.close()
            raise CodexExecError("Codex exec aborted before start")

        try:
            child.stdin.write(args.input)
            child.stdin.close()
        except OSError as exc:
            terminate_child(child)
            raise CodexExecError(f"Failed to write input to codex process: {exc}") from exc

        if is_signal_aborted(args.signal):
            terminate_child(child)
            _ = child.stderr.read()
            child.stderr.close()
            raise CodexExecError("Codex exec aborted")

        aborted = False
        try:
            for line in child.stdout:
                if is_signal_aborted(args.signal):
                    aborted = True
                    break
                yield line.rstrip("\r\n")
        except GeneratorExit:
            terminate_child(child)
            child.stderr.close()
            raise
        finally:
            child.stdout.close()

        if aborted:
            terminate_child(child)
            stderr = child.stderr.read()
            child.stderr.close()
            raise CodexExecError(build_abort_message(stderr))

        exit_code = child.wait()
        stderr = child.stderr.read()
        child.stderr.close()

        if exit_code != 0:
            raise CodexExecError(f"Codex exec exited with code {exit_code}: {stderr}")

    def build_env(self, base_url: str | None, api_key: str | None) -> dict[str, str]:
        env: dict[str, str]
        if self._env_override is None:
            env = os.environ.copy()
        else:
            env = dict(self._env_override)

        if INTERNAL_ORIGINATOR_ENV not in env:
            env[INTERNAL_ORIGINATOR_ENV] = PYTHON_SDK_ORIGINATOR
        if base_url is not None:
            env["OPENAI_BASE_URL"] = base_url
        if api_key is not None:
            env["CODEX_API_KEY"] = api_key
        return env


def terminate_child(child: subprocess.Popen[str]) -> None:
    try:
        child.kill()
    except Exception:
        pass
    try:
        child.wait()
    except Exception:
        pass


def build_abort_message(stderr: str) -> str:
    if stderr == "":
        return "Codex exec aborted"
    return f"Codex exec aborted: {stderr}"


def is_signal_aborted(signal: CancelSignal | None) -> bool:
    if signal is None:
        return False
    if isinstance(signal, SupportsAborted):
        return signal.aborted
    if isinstance(signal, SupportsIsSet):
        return signal.is_set()
    raise TypeError("signal must expose `aborted` or `is_set()`")


def serialize_config_overrides(config_overrides: CodexConfigObject) -> list[str]:
    overrides: list[str] = []
    flatten_config_overrides(config_overrides, "", overrides)
    return overrides


def flatten_config_overrides(
    value: CodexConfigValue | CodexConfigObject, prefix: str, overrides: list[str]
) -> None:
    if not isinstance(value, dict):
        if prefix == "":
            raise ValueError("Codex config overrides must be a plain object")
        overrides.append(f"{prefix}={to_toml_value(value, prefix)}")
        return

    entries = list(value.items())
    if prefix == "" and not entries:
        return
    if prefix != "" and not entries:
        overrides.append(f"{prefix}={{}}")
        return

    for key, child in entries:
        if not isinstance(key, str) or key == "":
            raise ValueError("Codex config override keys must be non-empty strings")
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            flatten_config_overrides(child, path, overrides)
        else:
            overrides.append(f"{path}={to_toml_value(child, path)}")


def to_toml_value(value: CodexConfigValue, path: str) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return format_toml_bool(value)
    if isinstance(value, int):
        return f"{value}"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Codex config override at {path} must be a finite number")
        return f"{value}"
    if isinstance(value, list):
        rendered_items = [
            to_toml_value(item, f"{path}[{index}]") for index, item in enumerate(value)
        ]
        return f"[{', '.join(rendered_items)}]"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, child in value.items():
            if not isinstance(key, str) or key == "":
                raise ValueError("Codex config override keys must be non-empty strings")
            parts.append(f"{format_toml_key(key)} = {to_toml_value(child, f'{path}.{key}')}")
        return f"{{{', '.join(parts)}}}"
    if value is None:
        raise ValueError(f"Codex config override at {path} cannot be null")
    raise ValueError(f"Unsupported Codex config override value at {path}: {type(value).__name__}")


def format_toml_key(key: str) -> str:
    if TOML_BARE_KEY.match(key):
        return key
    return json.dumps(key)


def format_toml_bool(value: bool) -> str:
    return "true" if value else "false"
