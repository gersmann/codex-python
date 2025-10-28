from __future__ import annotations


class CodexError(RuntimeError):
    """Base error for the Python Codex SDK."""


class CodexExecError(CodexError):
    """Raised when the Codex CLI process fails."""


class CodexParseError(CodexError):
    """Raised when streaming JSONL events cannot be parsed."""


class ThreadRunError(CodexError):
    """Raised when a run or stream fails before turn completion."""
