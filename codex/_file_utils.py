from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path_str = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
