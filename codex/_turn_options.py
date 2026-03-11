"""Shared turn-option helpers for structured-output runs."""

from __future__ import annotations

from pydantic import BaseModel

from codex.app_server.options import AppServerTurnOptions
from codex.output_schema import resolve_model_output_schema


def with_model_output_schema(
    options: AppServerTurnOptions | None,
    model_type: type[BaseModel],
    *,
    owner: str,
    option_model: type[AppServerTurnOptions] = AppServerTurnOptions,
) -> AppServerTurnOptions:
    if options is None:
        return option_model(output_schema=model_type)
    return options.model_copy(
        update={
            "output_schema": resolve_model_output_schema(
                options.output_schema,
                model_type,
                owner=owner,
            )
        }
    )
