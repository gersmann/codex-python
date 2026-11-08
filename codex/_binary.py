from __future__ import annotations

from pathlib import Path

from codex.errors import CodexExecError

RUNTIME_PACKAGE = "openai-codex-cli-bin"


class BundledCodexNotFoundError(CodexExecError):
    """The pinned Codex runtime package is not installed or is incomplete."""


def bundled_codex_path() -> Path:
    """Return the `codex` executable shipped by the pinned runtime package."""
    try:
        from codex_cli_bin import bundled_codex_path as runtime_codex_path
    except ImportError as exc:
        raise BundledCodexNotFoundError(
            f"{RUNTIME_PACKAGE} is not installed. Reinstall codex-python, install Codex on PATH, "
            "or provide codex_path_override."
        ) from exc
    try:
        return Path(runtime_codex_path())
    except FileNotFoundError as exc:
        raise BundledCodexNotFoundError(str(exc)) from exc


def bundled_path_dirs() -> tuple[Path, ...]:
    """Return helper directories (such as ripgrep) to put on the bundled Codex PATH."""
    try:
        from codex_cli_bin import bundled_path_dir
    except ImportError:
        return ()
    try:
        path_dir = bundled_path_dir()
    except FileNotFoundError:
        return ()
    return () if path_dir is None else (Path(path_dir),)
