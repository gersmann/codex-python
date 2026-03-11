from __future__ import annotations

import pytest
from pydantic import BaseModel

from codex.output_schema import normalize_output_schema


class _AnswerModel(BaseModel):
    answer: str


def test_normalize_output_schema_accepts_none_mapping_and_model_type() -> None:
    schema_mapping = {"type": "object", "properties": {"answer": {"type": "string"}}}

    assert normalize_output_schema(None) is None
    assert normalize_output_schema(schema_mapping) == schema_mapping
    assert normalize_output_schema(_AnswerModel) == _AnswerModel.model_json_schema()


def test_normalize_output_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="JSON object or a Pydantic model class"):
        normalize_output_schema(["not", "valid"])  # type: ignore[arg-type]
