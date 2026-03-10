#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path


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


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="codex-app-server-schema-") as temp_dir:
        schema_dir = Path(temp_dir) / "schemas"
        schema_dir.mkdir()
        schema_command = [
            args.codex_bin,
            "app-server",
            "generate-json-schema",
            "--out",
            str(schema_dir),
        ]
        if args.experimental:
            schema_command.append("--experimental")
        run_command(schema_command)

        schema_path = schema_dir / "codex_app_server_protocol.schemas.json"
        run_command(
            [
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
                "--use-title-as-name",
                "--enum-field-as-literal",
                "all",
                "--output",
                str(output_path),
            ]
        )
    run_command(["python", "scripts/postprocess_protocol_types.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
