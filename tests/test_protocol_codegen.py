from __future__ import annotations

from pathlib import Path


def test_generated_protocol_types_do_not_use_legacy_conint() -> None:
    content = Path("codex/protocol/types.py").read_text(encoding="utf-8")

    assert " conint" not in content
    assert "conint(" not in content
