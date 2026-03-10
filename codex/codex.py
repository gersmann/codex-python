from __future__ import annotations

from codex.exec import CodexExec
from codex.options import CodexOptions, ThreadOptions
from codex.thread import Thread


class Codex:
    """Main entrypoint for interacting with Codex threads."""

    def __init__(self, options: CodexOptions | None = None) -> None:
        """Create a CLI-backed Codex client."""
        resolved = options or CodexOptions()
        self._exec = CodexExec(
            resolved.codex_path_override,
            env_override=resolved.env,
            config_overrides=resolved.config,
        )
        self._options = resolved

    def start_thread(self, options: ThreadOptions | None = None) -> Thread:
        """Create a new local thread wrapper."""
        return Thread(self._exec, self._options, options or ThreadOptions())

    def resume_thread(self, id: str, options: ThreadOptions | None = None) -> Thread:
        """Resume a previously created thread by id."""
        if id == "":
            raise ValueError("id must be non-empty")
        return Thread(self._exec, self._options, options or ThreadOptions(), id)
