from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from codex._file_utils import atomic_write_text
from codex.output_schema import OutputSchemaInput, normalize_output_schema


@dataclass(slots=True, frozen=True)
class OutputSchemaFile:
    schema_path: str | None
    schema_dir: str | None

    def cleanup(self) -> None:
        if self.schema_dir is not None:
            shutil.rmtree(self.schema_dir, ignore_errors=True)


def create_output_schema_file(schema: OutputSchemaInput | None) -> OutputSchemaFile:
    normalized_schema = normalize_output_schema(schema)
    if normalized_schema is None:
        return OutputSchemaFile(schema_path=None, schema_dir=None)

    schema_dir = Path(tempfile.mkdtemp(prefix="codex-output-schema-"))
    schema_path = schema_dir / "schema.json"
    try:
        atomic_write_text(schema_path, json.dumps(normalized_schema))
    except Exception:
        shutil.rmtree(schema_dir, ignore_errors=True)
        raise
    return OutputSchemaFile(schema_path=str(schema_path), schema_dir=str(schema_dir))
