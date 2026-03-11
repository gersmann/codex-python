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


def resolve_model_output_schema(
    schema: OutputSchemaInput | None,
    model_type: type[BaseModel],
    *,
    owner: str,
) -> OutputSchemaInput:
    if schema is None:
        return model_type
    if schema is model_type:
        return schema
    if normalize_output_schema(schema) == normalize_output_schema(model_type):
        return schema
    raise ValueError(
        f"{owner} received both model_type and turn_options.output_schema with different "
        "schemas; pass only one or make them match"
    )
