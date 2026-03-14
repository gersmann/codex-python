from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codex.errors import CodexError

if TYPE_CHECKING:
    from codex.protocol import types as protocol


class AppServerError(CodexError):
    """Base error for Codex app-server interactions."""


class AppServerConnectionError(AppServerError):
    """Raised when the app-server transport cannot be started or used."""


class AppServerClosedError(AppServerConnectionError):
    """Raised when the app-server connection has already been closed."""


class AppServerProtocolError(AppServerError):
    """Raised when a received app-server message is malformed."""


class AppServerRpcError(AppServerError):
    """Raised when app-server returns a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(f"app-server RPC error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


class AppServerTurnError(AppServerError):
    """Raised when a turn reaches a terminal non-success status."""

    def __init__(self, message: str, *, turn: protocol.Turn | None = None) -> None:
        super().__init__(message)
        self.turn = turn
        self.terminal_status = None if turn is None else turn.status.root
