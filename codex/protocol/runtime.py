from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator

from pydantic import BaseModel

from .types import EventMsg


class Event(BaseModel):
    """Protocol event envelope emitted by `codex exec --json`."""

    id: str
    msg: EventMsg


def stream_exec_events(
    prompt: str,
    *,
    executable: str = "codex",
    model: str | None = None,
    full_auto: bool = False,
    cd: str | None = None,
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
    if full_auto:
        cmd.append("--full-auto")
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
