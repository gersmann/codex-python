"""codex

Python interface for the Codex CLI.

Usage:
    from codex import run_exec
    events = run_exec("explain this codebase to me")
"""

from .api import (
    CodexClient,
    CodexError,
    CodexNativeError,
    Conversation,
    run_exec,
)
from .config import CodexConfig
from .event import Event
from .protocol.types import EventMsg

__all__ = [
    "__version__",
    "CodexError",
    "CodexNativeError",
    "CodexClient",
    "Conversation",
    "run_exec",
    "Event",
    "EventMsg",
    "CodexConfig",
]

# Package version. Kept in sync with Cargo.toml via CI before builds.
__version__ = "0.2.11"
