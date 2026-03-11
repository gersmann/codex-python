#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from codex._file_utils import atomic_write_text

type SchemaNode = dict[str, object]

TARGETS = [
    ("EventMsg", "type"),
    ("ClientRequest", "method"),
    ("ServerRequest", "method"),
    ("ServerNotification", "method"),
    ("InputItem", "type"),
]


def camelize(s: str) -> str:
    parts = [p for p in s.replace("-", "_").replace(" ", "_").split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _definitions_node(schema: SchemaNode) -> tuple[dict[str, object], str] | None:
    for key in ("definitions", "$defs"):
        defs = schema.get(key)
        if isinstance(defs, dict):
            return defs, key
    return None


def _tag_variants(node: SchemaNode) -> list[SchemaNode] | None:
    one_of = node.get("oneOf") or node.get("anyOf")
    if not isinstance(one_of, list):
        return None
    return [variant for variant in one_of if isinstance(variant, dict)]


def _tag_value(properties: object, tag_key: str) -> str | None:
    if not isinstance(properties, dict):
        return None
    tag = properties.get(tag_key)
    if not isinstance(tag, dict):
        return None
    enum = tag.get("enum")
    if isinstance(enum, list) and enum and isinstance(enum[0], str):
        return enum[0]
    const = tag.get("const")
    if isinstance(const, str):
        return const
    return None


def _walk_schema(node: object, visit: Callable[[SchemaNode], None]) -> None:
    if isinstance(node, dict):
        visit(node)
        for key in ("items", "additionalProperties", "not"):
            child = node.get(key)
            if isinstance(child, dict):
                _walk_schema(child, visit)
        for key in ("anyOf", "oneOf", "allOf"):
            children = node.get(key)
            if isinstance(children, list):
                for child in children:
                    _walk_schema(child, visit)
        for key in ("definitions", "$defs", "patternProperties"):
            children = node.get(key)
            if isinstance(children, dict):
                for child in children.values():
                    _walk_schema(child, visit)
        return
    if isinstance(node, list):
        for child in node:
            _walk_schema(child, visit)


def _nullable(prop_schema: object) -> bool:
    if not isinstance(prop_schema, dict):
        return False
    field_type = prop_schema.get("type")
    if field_type == "null":
        return True
    if isinstance(field_type, list) and "null" in field_type:
        return True
    for key in ("anyOf", "oneOf"):
        variants = prop_schema.get(key)
        if not isinstance(variants, list):
            continue
        if any(isinstance(variant, dict) and variant.get("type") == "null" for variant in variants):
            return True
    return False


def _normalize_numeric_type(value: object) -> tuple[object, bool]:
    if value == "number":
        return "integer", True
    if not isinstance(value, list) or "number" not in value:
        return value, False
    normalized = ["integer" if item == "number" else item for item in value]
    return _dedupe_preserve_order(normalized), True


def _replace_number_with_integer(node: SchemaNode) -> bool:
    changed = False
    normalized_type, type_changed = _normalize_numeric_type(node.get("type"))
    if type_changed:
        node["type"] = normalized_type
        changed = True
    for key in ("anyOf", "oneOf"):
        variants = node.get(key)
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            normalized_variant_type, variant_changed = _normalize_numeric_type(variant.get("type"))
            if variant_changed:
                variant["type"] = normalized_variant_type
                changed = True
    return changed


def _duration_union(description: object) -> list[SchemaNode]:
    description_field = {"description": description} if isinstance(description, str) else {}
    return [
        {"type": "string", **description_field},
        {
            "type": "object",
            "properties": {
                "secs": {"type": "integer"},
                "nanos": {"type": "integer"},
            },
            "required": ["secs", "nanos"],
            "additionalProperties": False,
            **description_field,
        },
    ]


def add_titles(schema: dict) -> tuple[bool, int]:
    definitions = _definitions_node(schema)
    if definitions is None:
        return (False, 0)
    defs, base_key = definitions
    changed = False
    added = 0
    for name, tag_key in TARGETS:
        node = defs.get(name)
        if not isinstance(node, dict):
            continue
        variants = _tag_variants(node)
        if variants is None:
            continue
        one_of = node.get("oneOf") or node.get("anyOf")
        if not isinstance(one_of, list):
            continue
        for index, variant in enumerate(one_of):
            if not isinstance(variant, dict):
                continue
            tag_value = _tag_value(variant.get("properties"), tag_key)
            if tag_value is None:
                continue
            title = f"{name}_{camelize(tag_value)}"
            variant["title"] = title
            if title not in defs:
                defs[title] = variant
                changed = True
                added += 1
            one_of[index] = {"$ref": f"#/{base_key}/{title}"}
    return changed, added


def relax_required_for_nullables(schema: dict) -> tuple[bool, int]:
    """Recursively remove nullable properties from 'required' arrays.

    Applies to the whole schema tree, not just top-level $defs/definitions, to
    capture inline object schemas generated within oneOf/anyOf branches.
    """
    changed = False
    count = 0

    def visit(node: SchemaNode) -> None:
        nonlocal changed, count
        properties = node.get("properties")
        required = node.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            return
        new_required = [name for name in required if not _nullable(properties.get(name))]
        if len(new_required) == len(required):
            return
        node["required"] = new_required
        changed = True
        count += len(required) - len(new_required)

    _walk_schema(schema, visit)
    return changed, count


def enforce_request_id_integer(schema: dict) -> bool:
    # Force RequestId to be string|integer (not number) so Python maps to str|int
    defs = schema.get("definitions") or schema.get("$defs")
    if not isinstance(defs, dict):
        return False
    node = defs.get("RequestId")
    if not isinstance(node, dict):
        return False
    current = node.get("type")
    desired = ["string", "integer"]
    if current != desired:
        node["type"] = desired
        # remove other conflicting keys if any
        for k in ("anyOf", "oneOf"):
            if k in node:
                node.pop(k)
        return True
    return False


def enforce_exec_exit_code_integer(schema: dict) -> bool:
    # Force ExecCommandEndEvent.exit_code to integer
    defs = schema.get("definitions") or schema.get("$defs")
    if not isinstance(defs, dict):
        return False
    node = defs.get("ExecCommandEndEvent")
    if not isinstance(node, dict):
        return False
    props = node.get("properties")
    if not isinstance(props, dict):
        return False
    exit_node = props.get("exit_code")
    if not isinstance(exit_node, dict):
        return False
    if exit_node.get("type") != "integer":
        exit_node["type"] = "integer"
        return True
    return False


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Return a new list with duplicates removed, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


INTEGER_FIELDS = {
    # Exec
    "exit_code",
    # Token usage counters
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
    # Context window capacity
    "model_context_window",
    # History identifiers and counters
    "log_id",
    "history_log_id",
    "history_entry_count",
    "offset",
}


def enforce_integer_fields(schema: dict) -> int:
    """Walk the JSON Schema and coerce selected numeric fields to integer.

    Applies to both hoisted $defs and inline subschemas to avoid mismatches
    between event structs and EventMsg wrappers.
    """
    changed = 0

    def visit(node: SchemaNode) -> None:
        nonlocal changed
        properties = node.get("properties")
        if not isinstance(properties, dict):
            return
        for name, sub_schema in properties.items():
            if (
                name in INTEGER_FIELDS
                and isinstance(sub_schema, dict)
                and _replace_number_with_integer(sub_schema)
            ):
                changed += 1

    _walk_schema(schema, visit)
    return changed


def enforce_duration_union(schema: dict) -> int:
    """Allow duration fields to be either string or {secs,nanos} object.

    Some upstream emitters serialize Rust `Duration` as an object
    `{secs, nanos}` while the TypeScript schema uses `string`.
    To tolerate both without breaking older clients, convert any
    property named `duration` that is currently `type: string` into
    a `oneOf: [string, {secs:int, nanos:int}]`.
    Applies recursively across the schema tree.
    """
    changed = 0

    def visit(node: SchemaNode) -> None:
        nonlocal changed
        properties = node.get("properties")
        if not isinstance(properties, dict):
            return
        duration = properties.get("duration")
        if not isinstance(duration, dict) or duration.get("type") != "string":
            return
        description = duration.get("description")
        duration.clear()
        duration["oneOf"] = _duration_union(description)
        changed += 1

    _walk_schema(schema, visit)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-process generated JSON Schema: add titles/hoist, integer coercions, and optional tweaks",
    )
    parser.add_argument(
        "schema",
        nargs="?",
        default=Path(".generated/schema/protocol.schema.json"),
        type=Path,
        help="Path to protocol.schema.json",
    )
    parser.add_argument(
        "--relax-nullable-required",
        action="store_true",
        help="If set, remove nullable properties from 'required' to make them optional in Python.",
    )
    args = parser.parse_args()

    path: Path = args.schema
    data = json.loads(path.read_text())
    t_changed, t_added = add_titles(data)
    r_changed = False
    r_count = 0
    if args.relax_nullable_required:
        r_changed, r_count = relax_required_for_nullables(data)
    id_fixed = enforce_request_id_integer(data)
    exit_fixed = enforce_exec_exit_code_integer(data)
    coerced = enforce_integer_fields(data)
    durations = enforce_duration_union(data)
    if t_changed or r_changed or id_fixed or exit_fixed or coerced or durations:
        atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(
        f"Schema postprocess: titles+hoist added={t_added}, relaxed_required={r_count if args.relax_nullable_required else 0}, "
        f"requestId_fixed={'yes' if id_fixed else 'no'}, exit_code_fixed={'yes' if exit_fixed else 'no'}, integers_coerced={coerced}, durations_patched={durations} in {path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
