from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codex.protocol import types as protocol


class CodexError(RuntimeError):
    """Base error for the Python Codex SDK."""


class CodexExecError(CodexError):
    """Raised when the Codex CLI process fails."""


class CodexParseError(CodexError):
    """Raised when streaming JSONL events cannot be parsed."""


class ThreadRunError(CodexError):
    """Raised when a run or stream fails before turn completion."""

    def __init__(self, message: str, *, turn: protocol.Turn | None = None) -> None:
        super().__init__(message)
        self.turn = turn
        self.terminal_status = None if turn is None else turn.status.root
