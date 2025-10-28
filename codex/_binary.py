from __future__ import annotations

import platform
from pathlib import Path

from codex.errors import CodexExecError


def resolve_target_triple(system_name: str | None = None, machine_name: str | None = None) -> str:
    system = (system_name or platform.system()).lower()
    machine = (machine_name or platform.machine()).lower()

    if system in {"linux", "android"}:
        if machine in {"x86_64", "amd64"}:
            return "x86_64-unknown-linux-musl"
        if machine in {"aarch64", "arm64"}:
            return "aarch64-unknown-linux-musl"
    elif system == "darwin":
        if machine in {"x86_64", "amd64"}:
            return "x86_64-apple-darwin"
        if machine in {"aarch64", "arm64"}:
            return "aarch64-apple-darwin"
    elif system in {"windows", "win32"}:
        if machine in {"x86_64", "amd64"}:
            return "x86_64-pc-windows-msvc"
        if machine in {"aarch64", "arm64"}:
            return "aarch64-pc-windows-msvc"

    raise CodexExecError(f"Unsupported platform: {system} ({machine})")


def bundled_codex_path(target_triple: str | None = None) -> Path:
    triple = target_triple or resolve_target_triple()
    package_root = Path(__file__).resolve().parent
    binary_name = "codex.exe" if "windows" in triple else "codex"
    binary_path = package_root / "vendor" / triple / "codex" / binary_name
    if not binary_path.exists():
        raise CodexExecError(
            "Bundled codex binary not found at "
            f"{binary_path}. Install a platform wheel or provide codex_path_override."
        )
    return binary_path
