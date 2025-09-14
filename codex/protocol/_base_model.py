from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict


class BaseModelWithExtras(BaseModel):
    model_config = ConfigDict(extra="allow")
