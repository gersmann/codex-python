from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict

from .protocol.types import EventMsg


class AnyEventMsg(BaseModel):
    """Fallback event payload that preserves the original `type` and fields.

    Accepts any additional keys to retain upstream payloads when strict
    validation fails for generated models.
    """

    type: str

    # Allow arbitrary extra fields so we don't lose information
    model_config = ConfigDict(extra="allow")


class Event(BaseModel):
    """Protocol event envelope with typed `msg` (union of EventMsg_*)."""

    id: str
    msg: EventMsg | AnyEventMsg

    # Allow forward compatibility with additional envelope fields
    model_config = ConfigDict(extra="allow")
