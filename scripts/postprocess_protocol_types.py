#!/usr/bin/env python3
"""Apply the named post-generation passes for protocol type cleanup.

Pipeline contract:
1. Repair recursive forward references emitted by datamodel-code-generator.
2. Normalize union RootModel wrappers that would fail at class creation time.
3. Expose typed value aliases for generated union RootModel wrappers.
4. Ensure generated-file directives are present.
5. Rename known unreadable generated aliases.
6. Append required model_rebuild() calls for wrapper unions.
7. Deduplicate rebuild calls from repeated runs.
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROTOCOL_TYPES_PATH = Path("codex/protocol/types.py")
UNION_WRAPPER_NAMES = (
    "EventMsg",
    "ClientRequest",
    "ServerRequest",
    "ServerNotification",
    "InputItem",
)
RENAME_MAP = {
    "Record3Cstring2Cnever3E": "EmptyObject",
}
ROOT_MODEL_DEFAULT_REPLACEMENTS = {
    "PermissionGrantScope": ("turn", 'PermissionGrantScope("turn")'),
    "NetworkAccess": ("restricted", 'NetworkAccess("restricted")'),
    "CommandExecutionSource": ("agent", 'CommandExecutionSource("agent")'),
    "HookSource": ("unknown", 'HookSource("unknown")'),
}
ROOT_MODEL_LIST_DEFAULT_REPLACEMENTS = {
    "InputModality": (
        ("text", "image"),
        '[InputModality("text"), InputModality("image")]',
    ),
}


@dataclass(frozen=True)
class TransformPass:
    name: str
    transform: Callable[[str], str]


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path_str = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_path_str)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def rewrite_recursive_jsonvalue_forward_refs(text: str) -> str:
    text = re.sub(r"RootModel\[([^\]]*?)JsonValue([^\]]*?)\]", r"RootModel[\1'JsonValue'\2]", text)
    text = re.sub(r"list\[JsonValue\]", "list['JsonValue']", text)
    text = re.sub(r"dict\[str, JsonValue\]", "dict[str, 'JsonValue']", text)
    return text.replace("''JsonValue''", "'JsonValue'")


def normalize_union_rootmodel_wrappers(text: str) -> str:
    text = re.sub(
        r"class\s+(EventMsg|ClientRequest|ServerRequest|ServerNotification|InputItem)\s*\(\s*RootModel\[[^\]]+\]\s*\):",
        lambda match: f"class {match.group(1)}(RootModel):",
        text,
    )
    return re.sub(
        r"'((?:EventMsg|ClientRequest|ServerRequest|ServerNotification|InputItem)[A-Za-z0-9_]+)'",
        r"\1",
        text,
    )


def expose_union_rootmodel_value_aliases(text: str) -> str:
    for wrapper_name in UNION_WRAPPER_NAMES:
        alias_name = f"{wrapper_name}Value"
        if re.search(rf"^type\s+{alias_name}\s*=", text, flags=re.M):
            continue
        root_value = _extract_union_root_value(text, wrapper_name)
        if root_value is None:
            continue
        value_start, field_start, value_text = root_value
        alias_text = _format_root_value_alias(alias_name, value_text)
        text = text[:value_start] + f"        {alias_name}," + text[field_start:]
        class_match = re.search(rf"^class\s+{wrapper_name}\(\s*RootModel\s*\):", text, flags=re.M)
        if class_match is None:
            continue
        text = text[: class_match.start()] + alias_text + text[class_match.start() :]
    return text


def _extract_union_root_value(
    text: str,
    wrapper_name: str,
) -> tuple[int, int, str] | None:
    class_match = re.search(rf"^class\s+{wrapper_name}\(\s*RootModel\s*\):\n", text, flags=re.M)
    if class_match is None:
        return None
    next_class = re.search(r"^class\s+\w+\b", text[class_match.end() :], flags=re.M)
    class_end = len(text) if next_class is None else class_match.end() + next_class.start()
    root_prefix = "    root: Annotated[\n"
    root_start = text.find(root_prefix, class_match.end(), class_end)
    if root_start == -1:
        return None
    value_start = root_start + len(root_prefix)
    field_start = text.find("\n        Field(", value_start, class_end)
    if field_start == -1:
        return None
    value_text = text[value_start:field_start].rstrip()
    if not value_text.endswith(","):
        return None
    value_text = value_text[:-1].rstrip()
    if "\n" not in value_text:
        return None
    return value_start, field_start, value_text


def _format_root_value_alias(alias_name: str, value_text: str) -> str:
    alias_lines = []
    for line in value_text.splitlines():
        if line.startswith("        "):
            alias_lines.append(f"    {line[8:]}")
        else:
            alias_lines.append(f"    {line.lstrip()}")
    return f"type {alias_name} = (\n" + "\n".join(alias_lines) + "\n)\n\n"


def ensure_generated_file_directives(text: str) -> str:
    lines = text.splitlines()
    directive_insert_at = 1
    for idx, line in enumerate(lines[:10]):
        if line.startswith("# generated by"):
            directive_insert_at = idx + 1
            break

    if "from __future__ import annotations" not in lines[:10]:
        lines.insert(directive_insert_at, "from __future__ import annotations")
        directive_insert_at += 1
    if "# ruff: noqa: F821" not in lines[:8]:
        lines.insert(directive_insert_at, "# ruff: noqa: F821")

    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def rename_generated_aliases(text: str) -> str:
    for old, new in RENAME_MAP.items():
        text = re.sub(rf"\b{old}\b", new, text)
    return text


def normalize_root_model_defaults(text: str) -> str:
    for model_name, (literal_value, replacement) in ROOT_MODEL_DEFAULT_REPLACEMENTS.items():
        text = re.sub(
            rf"(\b\w+:\s*Annotated\[{model_name} \| None, Field\(validate_default=True\)\]\s*=\s*)[\"']{literal_value}[\"']",
            rf"\1{replacement}",
            text,
        )
    for model_name, (literal_values, replacement) in ROOT_MODEL_LIST_DEFAULT_REPLACEMENTS.items():
        literal_pattern = r"\s*,\s*".join(
            rf"[\"']{literal_value}[\"']" for literal_value in literal_values
        )
        text = re.sub(
            rf"(\b\w+:\s*Annotated\[list\[{model_name}\] \| None, Field\(validate_default=True\)\]\s*=\s*)\[\s*{literal_pattern}\s*,?\s*\]",
            rf"\1{replacement}",
            text,
            flags=re.S,
        )
    return text


def _replace_read_only_access_default(text: str, field_name: str) -> str:
    pattern = (
        rf"(\b{field_name}:\s*Annotated\[ReadOnlyAccess \| None, "
        r"Field\(validate_default=True\)\]\s*=\s*)"
        r"\{\s*[\"']type[\"']:\s*[\"']fullAccess[\"']\s*\}"
    )
    return re.sub(
        pattern,
        r'\1ReadOnlyAccess.model_validate({"type": "fullAccess"})',
        text,
        flags=re.S,
    )


def normalize_read_only_access_defaults(text: str) -> str:
    text = _replace_read_only_access_default(text, "access")
    return _replace_read_only_access_default(text, "readOnlyAccess")


def append_union_wrapper_rebuilds(text: str) -> str:
    trailer: list[str] = []
    for name in UNION_WRAPPER_NAMES:
        if re.search(rf"^class\s+{name}\(\s*RootModel\s*\):", text, flags=re.M):
            trailer.append(f"{name}.model_rebuild()")
    if not trailer:
        return text
    return text.rstrip() + "\n\n" + "\n".join(trailer) + "\n"


def deduplicate_model_rebuild_calls(text: str) -> tuple[str, int]:
    seen: set[str] = set()
    deduped_lines: list[str] = []
    removed = 0

    for line in text.splitlines():
        match = re.match(r"^(\w+)\.model_rebuild\(\)\s*$", line)
        if match is None:
            deduped_lines.append(line)
            continue
        name = match.group(1)
        if name in seen:
            removed += 1
            continue
        seen.add(name)
        deduped_lines.append(line)

    return "\n".join(deduped_lines) + ("\n" if text.endswith("\n") else ""), removed


POSTPROCESS_PASSES = (
    TransformPass(
        "rewrite recursive JsonValue forward refs", rewrite_recursive_jsonvalue_forward_refs
    ),
    TransformPass("normalize union RootModel wrappers", normalize_union_rootmodel_wrappers),
    TransformPass("expose union RootModel value aliases", expose_union_rootmodel_value_aliases),
    TransformPass("ensure generated file directives", ensure_generated_file_directives),
    TransformPass("rename unreadable generated aliases", rename_generated_aliases),
    TransformPass("normalize root model defaults", normalize_root_model_defaults),
    TransformPass("normalize read-only access defaults", normalize_read_only_access_defaults),
    TransformPass("append wrapper model_rebuild calls", append_union_wrapper_rebuilds),
)


def postprocess_types(text: str) -> tuple[str, int]:
    for transform_pass in POSTPROCESS_PASSES:
        text = transform_pass.transform(text)
    return deduplicate_model_rebuild_calls(text)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Postprocess generated Codex protocol types.")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_PROTOCOL_TYPES_PATH),
        help="Generated protocol types file to postprocess.",
    )
    return parser.parse_args(argv)


def postprocess_file(path: Path) -> int:
    original_text = path.read_text()
    updated_text, removed_rebuilds = postprocess_types(original_text)
    atomic_write_text(path, updated_text)

    pass_names = ", ".join(transform_pass.name for transform_pass in POSTPROCESS_PASSES)
    if removed_rebuilds:
        print(
            "Types postprocess: ran passes "
            f"[{pass_names}] and removed {removed_rebuilds} duplicate model_rebuild() lines"
        )
    else:
        print(f"Types postprocess: ran passes [{pass_names}]")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return postprocess_file(Path(args.path))


if __name__ == "__main__":
    raise SystemExit(main())
