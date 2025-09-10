#!/usr/bin/env python3
"""
Generate Python bindings from the TypeScript protocol types produced by
codex-proj/codex-rs/protocol-ts.

Steps:
1) Ensure TS has been generated to .generated/ts (see Makefile target).
2) Run this script to generate codex/protocol/types.py

The generator is intentionally conservative and supports a subset of TS:
- type aliases (string/number/boolean/bigint, string literal unions)
- object types (export type X = { ... })
- unions of object literals (e.g., ClientRequest)
- arrays (T[], Array<T>) and simple index signature maps

Optional fields: fields with `| null` are treated as NotRequired[X | None].

This generator is not a full TS parser; it assumes the style emitted by ts-rs.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

TS_DIR = Path(".generated/ts")
OUT_FILE = Path("codex/protocol/types.py")


@dataclass
class TypeAlias:
    name: str
    rhs: str  # Python type expression


@dataclass
class Field:
    name: str
    type_expr: str  # Python type expression
    optional: bool = False


@dataclass
class TypedDictDef:
    name: str
    fields: list[Field]


PY_HEADER = """# GENERATED CODE! DO NOT MODIFY BY HAND!
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


"""


def ts_basic_to_py(t: str) -> str:
    t = t.strip()
    # Literal string
    if re.fullmatch(r'"[^"\\]*"', t):
        return f"Literal[{t}]"
    # Basic primitives
    return (
        t.replace("string", "str")
        .replace("number", "float")
        .replace("boolean", "bool")
        .replace("bigint", "int")
        .replace("null", "None")
    )


def ts_type_to_py(t: str) -> str:
    t = t.strip()
    # Array<T>
    t = re.sub(r"Array<\s*([^>]+)\s*>", lambda m: f"list[{ts_type_to_py(m.group(1))}]", t)
    # T[]  (avoid matching '[]' in other contexts)
    t = re.sub(r"([A-Za-z0-9_\.]+)\s*\[\]", lambda m: f"list[{ts_type_to_py(m.group(1))}]", t)
    # Index signature maps { [key in string]?: JsonValue }
    t = re.sub(
        r"\{\s*\[key in string\]\?:\s*([^}]+)\s*\}",
        lambda m: f"dict[str, {ts_type_to_py(m.group(1))}]",
        t,
    )

    # Union types: split by | at top-level (naive but works for ts-rs output)
    parts = split_top_level_union(t)
    if len(parts) > 1:
        py_parts = [ts_type_to_py(p) for p in parts]
        return " | ".join(sorted(set(py_parts)))

    # Inline object type -> treat as generic mapping
    if t.startswith("{") and t.endswith("}"):
        return "dict[str, Any]"

    # Basic primitives and literals
    return ts_basic_to_py(t)


def split_top_level_union(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "{" or ch == "(" or ch == "<":
            depth += 1
            cur.append(ch)
        elif ch == "}" or ch == ")" or ch == ">":
            depth -= 1
            cur.append(ch)
        elif ch == "|" and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        parts.append("".join(cur).strip())
    return parts


def parse_object_fields(block: str) -> list[Field]:
    """Parse fields inside a { ... } object into Field structures.
    Expects lines with `name: type,` possibly with comments between.
    Supports quoted keys like "method".
    """
    # Remove comments (/** ... */)
    block = re.sub(r"/\*\*.*?\*/", "", block, flags=re.S)
    # Grab inside of outer braces
    m = re.search(r"\{(.*)\}\s*\Z", block, flags=re.S)
    if not m:
        return []
    body = m.group(1)
    fields: list[Field] = []
    # Split by commas not inside braces or angle brackets
    items = []
    depth = 0
    cur = []
    for ch in body:
        if ch in "{(<":
            depth += 1
            cur.append(ch)
        elif ch in ")}>":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        items.append(tail)

    for itm in items:
        if not itm:
            continue
        # Key may be quoted or unquoted
        km = re.match(r"^(?:\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))\s*:\s*(.+)$", itm)
        if not km:
            continue
        key = km.group(1) or km.group(2)
        ts_t = km.group(3).strip()
        # Remove trailing commas if present
        ts_t = ts_t.rstrip(",")

        # Optional if union contains null
        optional = False
        union_parts = split_top_level_union(ts_t)
        if any(p.strip() == "null" for p in union_parts):
            optional = True
            union_parts = [p for p in union_parts if p.strip() != "null"]
            ts_t = " | ".join(union_parts) if union_parts else "null"

        py_t = ts_type_to_py(ts_t)
        fields.append(Field(key, py_t, optional=optional))
    return fields


def generate_from_ts(ts_dir: Path) -> str:
    # First, load and pre-process all files
    files = [p for p in sorted(ts_dir.rglob("*.ts")) if p.name != "index.ts"]
    contents: dict[str, str] = {}
    for ts_file in files:
        raw = ts_file.read_text()
        c = re.sub(r"//.*", "", raw)
        c = re.sub(r"import[^;]+;", "", c, flags=re.S)
        c = c.strip()
        if not c:
            continue
        contents[ts_file.stem] = c

    # Pass 1: collect object-like aliases and interfaces into a registry
    objects: dict[str, list[Field]] = {}
    simple_aliases_source: dict[str, str] = {}
    unions_source: dict[str, str] = {}

    for _name, content_ in contents.items():
        m_type = re.search(
            r"export\s+type\s+(?P<name>[A-Za-z0-9_]+)\s*=\s*(?P<rhs>.+);\s*\Z", content_, flags=re.S
        )
        m_iface = re.search(
            r"export\s+interface\s+(?P<name>[A-Za-z0-9_]+)\s*(?P<body>\{.*\})\s*\Z",
            content_,
            flags=re.S,
        )
        if m_type:
            tname = m_type.group("name")
            rhs = m_type.group("rhs").strip()
            parts = split_top_level_union(rhs)
            if len(parts) > 1:
                unions_source[tname] = rhs
                continue
            if rhs.startswith("{"):
                objects[tname] = parse_object_fields(rhs)
            else:
                simple_aliases_source[tname] = rhs
            continue
        if m_iface:
            iname = m_iface.group("name")
            body = m_iface.group("body")
            objects[iname] = parse_object_fields(body)

    # Pass 2: emit structures and unions using the registry
    aliases: list[TypeAlias] = []
    tdicts: list[TypedDictDef] = []
    union_aliases: list[TypeAlias] = []

    # Emit object aliases/interfaces as models
    for obj_name, fields in sorted(objects.items()):
        tdicts.append(TypedDictDef(obj_name, fields))

    # Emit unions (including intersection merges)
    for uname, rhs in sorted(unions_source.items()):
        if uname == "JsonValue":
            # We'll map this to Any later
            continue
        parts = split_top_level_union(rhs)
        variant_names: list[str] = []
        for p in parts:
            p = p.strip()
            # Split intersections at top level
            inters = split_top_level_intersection(p)
            merged_fields: list[Field] = []
            for comp in inters:
                comp = comp.strip()
                if comp.startswith("{"):
                    merged_fields.extend(parse_object_fields(comp))
                else:
                    # Referenced type name
                    ref = re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", comp)
                    if ref and comp in objects:
                        merged_fields.extend(objects[comp])
            # Derive variant class name from 'type' or 'method' literal
            tag = next(
                (
                    f
                    for f in merged_fields
                    if f.name in {"type", "method"} and f.type_expr.startswith("Literal[")
                ),
                None,
            )
            if tag:
                lit = tag.type_expr[len("Literal[") : -1]
                tag_name = re.sub(r"[^A-Za-z0-9]+", "_", lit.strip('"'))
                cls_name = f"{uname}_{camelize(tag_name)}"
            else:
                cls_name = f"{uname}_Variant{len(variant_names) + 1}"
            tdicts.append(TypedDictDef(cls_name, merged_fields))
            variant_names.append(cls_name)
        union_aliases.append(TypeAlias(uname, " | ".join(variant_names)))

    # Emit simple aliases
    for aname, rhs in sorted(simple_aliases_source.items()):
        if re.fullmatch(r"Record\s*<\s*string\s*,\s*never\s*>", rhs):
            tdicts.append(TypedDictDef(aname, []))
        elif rhs.startswith("{"):
            # Should have been captured in objects, but keep safe
            tdicts.append(TypedDictDef(aname, parse_object_fields(rhs)))
        else:
            aliases.append(TypeAlias(aname, ts_type_to_py(rhs)))

    # Ensure JsonValue alias exists
    aliases = [a for a in aliases if a.name != "JsonValue"]
    aliases.append(TypeAlias("JsonValue", "Any"))

    # Emit Python code
    out = [PY_HEADER]
    for td in tdicts:
        out.append(f"class {td.name}(BaseModel):\n")
        out.append("    model_config = ConfigDict(extra='ignore')\n")
        if not td.fields:
            out.append("    pass\n\n")
            continue
        for f in td.fields:
            if f.optional:
                out.append(f"    {f.name}: {f.type_expr} | None = None\n")
            else:
                out.append(f"    {f.name}: {f.type_expr}\n")
        out.append("\n")
    out.append("\n")
    for ua in union_aliases:
        out.append(f"{ua.name} = {ua.rhs}\n")
    out.append("\n")
    for a in aliases:
        out.append(f"{a.name} = {a.rhs}\n")
    return "".join(out)


def split_top_level_intersection(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch in "{(<":
            depth += 1
            cur.append(ch)
        elif ch in ")}>":
            depth -= 1
            cur.append(ch)
        elif ch == "&" and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def camelize(s: str) -> str:
    # newConversation -> NewConversation; web-search -> Web_search
    parts = re.split(r"[^A-Za-z0-9]+", s)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def main(argv: list[str]) -> int:
    ts_dir = Path(argv[1]) if len(argv) > 1 else TS_DIR
    py = generate_from_ts(ts_dir)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(py)
    print(f"Wrote {OUT_FILE} from {ts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
