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


def add_titles(schema: dict) -> bool:
    defs = schema.get("definitions") or schema.get("$defs")
    if not isinstance(defs, dict):
        return False
    changed = False
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
            # replace inline with $ref
            ref = {"$ref": f"#/definitions/{title}"}
            one_of[idx] = ref
    return changed


def main() -> int:
    path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".generated/schema/protocol.schema.json")
    )
    data = json.loads(path.read_text())
    if add_titles(data):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"Updated titles in {path}")
    else:
        print("No title updates applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
