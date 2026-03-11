#!/usr/bin/env python3
"""Generate protocol types through explicit schema, codegen, and postprocess stages."""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import tempfile
from pathlib import Path

SUBPROCESS_TIMEOUT_SECONDS = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Pydantic protocol models from codex app-server JSON Schema."
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable to use for schema generation.",
    )
    parser.add_argument(
        "--output",
        default="codex/protocol/types.py",
        help="Output path for generated protocol types.",
    )
    parser.add_argument(
        "--experimental",
        action="store_true",
        help="Include experimental methods and fields.",
    )
    return parser.parse_args()


def run_stage(name: str, command: list[str]) -> None:
    print(f"[protocol-gen] {name}")
    subprocess.run(command, check=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)  # nosec B603


def build_schema_export_command(
    *,
    codex_bin: str,
    schema_dir: Path,
    experimental: bool,
) -> list[str]:
    command = [
        codex_bin,
        "app-server",
        "generate-json-schema",
        "--out",
        str(schema_dir),
    ]
    if experimental:
        command.append("--experimental")
    return command


def build_datamodel_codegen_command(*, schema_path: Path, output_path: Path) -> list[str]:
    return [
        "uvx",
        "--from",
        "datamodel-code-generator",
        "datamodel-codegen",
        "--input",
        str(schema_path),
        "--input-file-type",
        "jsonschema",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.12",
        "--use-annotated",
        "--use-title-as-name",
        "--enum-field-as-literal",
        "all",
        "--output",
        str(output_path),
    ]


def export_protocol_schema(*, codex_bin: str, schema_dir: Path, experimental: bool) -> Path:
    schema_dir.mkdir()
    run_stage(
        "export app-server JSON Schema",
        build_schema_export_command(
            codex_bin=codex_bin,
            schema_dir=schema_dir,
            experimental=experimental,
        ),
    )
    return schema_dir / "codex_app_server_protocol.schemas.json"


def generate_protocol_models(*, schema_path: Path, output_path: Path) -> None:
    run_stage(
        "generate Pydantic models with datamodel-codegen",
        build_datamodel_codegen_command(schema_path=schema_path, output_path=output_path),
    )


def postprocess_protocol_models() -> None:
    run_stage(
        "postprocess generated protocol types", ["python", "scripts/postprocess_protocol_types.py"]
    )


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="codex-app-server-schema-") as temp_dir:
        schema_dir = Path(temp_dir) / "schemas"
        schema_path = export_protocol_schema(
            codex_bin=args.codex_bin,
            schema_dir=schema_dir,
            experimental=args.experimental,
        )
        generate_protocol_models(schema_path=schema_path, output_path=output_path)

    postprocess_protocol_models()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
