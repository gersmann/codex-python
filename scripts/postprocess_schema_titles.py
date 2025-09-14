#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
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


def main() -> int:
    path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".generated/schema/protocol.schema.json")
    )
    data = json.loads(path.read_text())
    t_changed, t_added = add_titles(data)
    r_changed, r_count = relax_required_for_nullables(data)
    id_fixed = enforce_request_id_integer(data)
    if t_changed or r_changed or id_fixed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(
        f"Schema postprocess: titles+hoist added={t_added}, relaxed_required={r_count}, requestId_fixed={'yes' if id_fixed else 'no'} in {path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
