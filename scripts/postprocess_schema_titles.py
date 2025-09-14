#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def add_titles(schema: dict) -> tuple[bool, int]:
    if isinstance(schema.get("definitions"), dict):
        defs = schema["definitions"]
        base_key = "definitions"
    elif isinstance(schema.get("$defs"), dict):
        defs = schema["$defs"]
        base_key = "$defs"
    else:
        return (False, 0)
    changed = False
    added = 0
    for name, tag_key in TARGETS:
        node = defs.get(name)
        if not isinstance(node, dict):
            continue
        one_of = node.get("oneOf") or node.get("anyOf")
        if not isinstance(one_of, list):
            continue
        for idx, subs in enumerate(list(one_of)):
            if not isinstance(subs, dict):
                continue
            props = subs.get("properties")
            if not isinstance(props, dict):
                continue
            tag = props.get(tag_key)
            if not isinstance(tag, dict):
                continue
            enum = tag.get("enum")
            # ts-json-schema-generator uses `const` instead of `enum` for tagged unions
            if not enum and isinstance(tag.get("const"), str):
                enum = [tag["const"]]
            if not (isinstance(enum, list) and enum and isinstance(enum[0], str)):
                continue
            variant = enum[0]
            title = f"{name}_{camelize(variant)}"
            # 1) set a title on the inline subschema for robustness
            subs["title"] = title
            # 2) hoist inline subschema to definitions and replace with $ref
            if title not in defs:
                defs[title] = subs
                changed = True
                added += 1
            # replace inline with $ref
            ref = {"$ref": f"#/{base_key}/{title}"}
            one_of[idx] = ref
    return changed, added


def relax_required_for_nullables(schema: dict) -> tuple[bool, int]:
    defs = schema.get("definitions") or schema.get("$defs")
    if not isinstance(defs, dict):
        return (False, 0)
    changed = False
    count = 0

    def prop_is_nullable(prop_schema: dict) -> bool:
        if not isinstance(prop_schema, dict):
            return False
        t = prop_schema.get("type")
        if isinstance(t, list) and "null" in t:
            return True
        for key in ("anyOf", "oneOf"):
            arr = prop_schema.get(key)
            if isinstance(arr, list):
                for sub in arr:
                    if isinstance(sub, dict) and sub.get("type") == "null":
                        return True
        return False

    for defn in defs.values():
        if not isinstance(defn, dict):
            continue
        props = defn.get("properties")
        req = defn.get("required")
        if not isinstance(props, dict) or not isinstance(req, list):
            continue
        new_req = [name for name in req if not prop_is_nullable(props.get(name, {}))]
        if len(new_req) != len(req):
            defn["required"] = new_req
            changed = True
            count += len(req) - len(new_req)
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


def _replace_number_with_integer(node: dict) -> bool:
    changed = False
    t = node.get("type")
    if t == "number":
        node["type"] = "integer"
        changed = True
    elif isinstance(t, list) and "number" in t:
        node["type"] = ["integer" if v == "number" else v for v in t]
        # dedupe while preserving order without side-effects in comprehensions
        node["type"] = _dedupe_preserve_order(node["type"])
        changed = True
    # Normalize anyOf/oneOf branches
    for key in ("anyOf", "oneOf"):
        arr = node.get(key)
        if isinstance(arr, list):
            for sub in arr:
                if isinstance(sub, dict) and sub.get("type") == "number":
                    sub["type"] = "integer"
                    changed = True
                elif isinstance(sub, dict) and isinstance(sub.get("type"), list):
                    sub_t = sub["type"]
                    if "number" in sub_t:
                        sub["type"] = ["integer" if v == "number" else v for v in sub_t]
                        # dedupe while preserving order
                        sub["type"] = _dedupe_preserve_order(sub["type"])
                        changed = True
    return changed


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

    def walk(node: object) -> None:
        nonlocal changed
        if isinstance(node, dict):
            # Adjust matching properties
            props = node.get("properties")
            if isinstance(props, dict):
                for name, sub in props.items():
                    if name in INTEGER_FIELDS and isinstance(sub, dict):
                        if _replace_number_with_integer(sub):
                            changed += 1
            # Recurse into common schema containers
            for k in ("items", "additionalProperties", "not"):
                if isinstance(node.get(k), dict):
                    walk(node[k])
            for k in ("anyOf", "oneOf", "allOf"):
                arr = node.get(k)
                if isinstance(arr, list):
                    for sub in arr:
                        walk(sub)
            # Dive into nested definition maps
            for k in ("definitions", "$defs", "patternProperties"):
                m = node.get(k)
                if isinstance(m, dict):
                    for sub in m.values():
                        walk(sub)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    walk(schema)
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
    if t_changed or r_changed or id_fixed or exit_fixed or coerced:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(
        f"Schema postprocess: titles+hoist added={t_added}, relaxed_required={r_count if args.relax_nullable_required else 0}, "
        f"requestId_fixed={'yes' if id_fixed else 'no'}, exit_code_fixed={'yes' if exit_fixed else 'no'}, integers_coerced={coerced} in {path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
