from __future__ import annotations

from typing import Any

from codex.errors import CodexError


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
