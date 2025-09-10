"""codex

Python interface for the Codex CLI.

Usage:
    from codex import run_exec
    output = run_exec("explain this codebase to me")
"""

from .api import (
    CodexClient,
    CodexError,
    CodexNotFoundError,
    CodexProcessError,
    find_binary,
    run_exec,
)

__all__ = [
    "__version__",
    "CodexError",
    "CodexNotFoundError",
    "CodexProcessError",
    "CodexClient",
    "find_binary",
    "run_exec",
]

# Managed by Hatch via pyproject.toml [tool.hatch.version]
__version__ = "0.1.2"
