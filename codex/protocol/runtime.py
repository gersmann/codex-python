from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel


class Event(BaseModel):
    """Protocol event envelope emitted by `codex exec --json`.

    Note: `msg` is kept as a raw mapping to preserve all fields from
    intersection types. If you need strong typing, try validating
    against `codex.protocol.types.EventMsg` manually.
    """

    id: str
    msg: dict[str, Any]


def stream_exec_events(
    prompt: str,
    *,
    executable: str = "codex",
    model: str | None = None,
    oss: bool = False,
    full_auto: bool = False,
    cd: str | None = None,
    skip_git_repo_check: bool = False,
    env: dict[str, str] | None = None,
) -> Iterator[Event]:
    """Spawn `codex exec --json` and yield Event objects from NDJSON stdout.

    Non-event lines (config summary, prompt echo) are ignored.
    """
    cmd: list[str] = [executable]
    if cd:
        cmd += ["--cd", cd]
    if model:
        cmd += ["-m", model]
    if oss:
        cmd.append("--oss")
    if full_auto:
        cmd.append("--full-auto")
    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    cmd += ["exec", "--json", prompt]

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **(env or {})},
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter out non-event helper lines
            if not isinstance(obj, dict):
                continue
            if "id" in obj and "msg" in obj:
                # Attempt to validate into our Pydantic Event model
                yield Event.model_validate(obj)

        # Drain stderr for diagnostics if the process failed
        ret = proc.wait()
        if ret != 0 and proc.stderr is not None:
            err = proc.stderr.read()
            raise RuntimeError(f"codex exec failed with {ret}: {err}")
