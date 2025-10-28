from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class OutputSchemaFile:
    schema_path: str | None
    schema_dir: str | None

    def cleanup(self) -> None:
        if self.schema_dir is not None:
            shutil.rmtree(self.schema_dir, ignore_errors=True)


def create_output_schema_file(schema: object | None) -> OutputSchemaFile:
    if schema is None:
        return OutputSchemaFile(schema_path=None, schema_dir=None)

    if not isinstance(schema, dict):
        raise ValueError("output_schema must be a plain JSON object")

    schema_dir = Path(tempfile.mkdtemp(prefix="codex-output-schema-"))
    schema_path = schema_dir / "schema.json"
    try:
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
    except Exception:
        shutil.rmtree(schema_dir, ignore_errors=True)
        raise
    return OutputSchemaFile(schema_path=str(schema_path), schema_dir=str(schema_dir))
