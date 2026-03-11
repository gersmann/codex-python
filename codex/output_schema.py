from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel

type OutputSchemaInput = Mapping[str, object] | type[BaseModel]


def normalize_output_schema(schema: OutputSchemaInput | None) -> dict[str, object] | None:
    if schema is None:
        return None
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return cast(dict[str, object], schema.model_json_schema())
    if isinstance(schema, Mapping):
        return dict(schema)
    raise ValueError("output_schema must be a JSON object or a Pydantic model class")
