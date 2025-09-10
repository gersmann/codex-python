from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict

from .protocol.types import EventMsg


class Event(BaseModel):
    """Protocol event envelope with typed `msg` (union of EventMsg_*)."""

    id: str
    msg: EventMsg

    # Allow forward compatibility with additional envelope fields
    model_config = ConfigDict(extra="allow")
