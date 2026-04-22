#!/usr/bin/env python3
"""Generate protocol types through explicit schema, codegen, and postprocess stages."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess  # nosec B404
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SUBPROCESS_TIMEOUT_SECONDS = 300
DATAMODEL_CODE_GENERATOR_PACKAGE = "datamodel-code-generator==0.56.1"
EXTRA_PROTOCOL_RESPONSE_SCHEMA_GLOB = "v2/*Response.json"


@dataclass(frozen=True)
class ModelDefinition:
    name: str
    text: str


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
        DATAMODEL_CODE_GENERATOR_PACKAGE,
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
        "--use-double-quotes",
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


def extra_protocol_schema_paths(schema_dir: Path) -> list[Path]:
    return sorted(schema_dir.glob(EXTRA_PROTOCOL_RESPONSE_SCHEMA_GLOB))


def generated_model_definitions(text: str) -> list[ModelDefinition]:
    tree = ast.parse(text)
    lines = text.splitlines()
    definitions = [
        ModelDefinition(
            name=node.name,
            text="\n".join(lines[node.lineno - 1 : node.end_lineno]).strip(),
        )
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.end_lineno is not None
    ]
    if definitions:
        return definitions
    raise ValueError("generated model file does not contain any class definitions")


def class_names(text: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"^class\s+(\w+)\b", text, flags=re.M)}


def append_generated_model_definitions(*, target_path: Path, generated_path: Path) -> int:
    target = target_path.read_text(encoding="utf-8")
    existing_names = class_names(target)
    new_definitions = [
        definition
        for definition in generated_model_definitions(generated_path.read_text(encoding="utf-8"))
        if definition.name not in existing_names
    ]
    if not new_definitions:
        return 0
    for definition in new_definitions:
        existing_names.add(definition.name)

    target_lines = target.splitlines()
    insert_at = next(
        (
            index
            for index, line in enumerate(target_lines)
            if re.match(r"^\w+\.model_rebuild\(\)\s*$", line)
        ),
        len(target_lines),
    )

    updated = (
        "\n".join(target_lines[:insert_at]).rstrip()
        + "\n\n"
        + "\n\n".join(definition.text for definition in new_definitions)
        + "\n\n"
        + "\n".join(target_lines[insert_at:]).lstrip()
    ).rstrip()
    target_path.write_text(updated + "\n", encoding="utf-8")
    return len(new_definitions)


def append_extra_protocol_models(*, schema_dir: Path, output_path: Path) -> None:
    schema_paths = extra_protocol_schema_paths(schema_dir)
    if not schema_paths:
        raise FileNotFoundError(
            f"no response schemas matched {EXTRA_PROTOCOL_RESPONSE_SCHEMA_GLOB!r} in {schema_dir}"
        )

    with tempfile.TemporaryDirectory(prefix="codex-extra-protocol-models-") as temp_dir:
        temp_path = Path(temp_dir)
        for schema_path in schema_paths:
            generated_path = temp_path / f"{schema_path.stem}.py"
            generate_protocol_models(schema_path=schema_path, output_path=generated_path)
            appended = append_generated_model_definitions(
                target_path=output_path,
                generated_path=generated_path,
            )
            if appended:
                print(
                    "[protocol-gen] appended "
                    f"{appended} models from {schema_path.relative_to(schema_dir)}"
                )


def build_postprocess_command(*, output_path: Path) -> list[str]:
    return [sys.executable, "scripts/postprocess_protocol_types.py", str(output_path)]


def postprocess_protocol_models(output_path: Path) -> None:
    run_stage(
        "postprocess generated protocol types",
        build_postprocess_command(output_path=output_path),
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
        append_extra_protocol_models(schema_dir=schema_dir, output_path=output_path)

    postprocess_protocol_models(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
