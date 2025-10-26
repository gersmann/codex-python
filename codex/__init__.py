"""codex

Python interface for the Codex CLI.

Usage:
    from codex import run_exec
    events = run_exec("explain this codebase to me")
"""

from .client import AsyncConversation, CodexClient, CodexError, CodexNativeError, Conversation
from .config import CodexConfig
from .event import Event
from .exec import run_exec, run_prompt, run_review
from .protocol.types import EventMsg

__all__ = [
    "__version__",
    "CodexError",
    "CodexNativeError",
    "CodexClient",
    "Conversation",
    "AsyncConversation",
    "run_prompt",
    "run_exec",
    "run_review",
    "Event",
    "EventMsg",
    "CodexConfig",
]

# Package version. Kept in sync with Cargo.toml via CI before builds.
__version__ = "0.3.0"
