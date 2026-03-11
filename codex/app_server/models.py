from __future__ import annotations

from pydantic import BaseModel, Field

from codex.protocol import types as protocol


class EmptyResult(BaseModel):
    pass


class InitializeResult(BaseModel):
    userAgent: str


class ThreadResult(BaseModel):
    thread: protocol.Thread


class ThreadListResult(BaseModel):
    data: list[protocol.Thread]
    nextCursor: str | None = None


class LoadedThreadsResult(BaseModel):
    data: list[str]


class TurnResult(BaseModel):
    turn: protocol.Turn


class ReviewResult(BaseModel):
    turn: protocol.Turn
    reviewThreadId: str


class TurnIdResult(BaseModel):
    turnId: str


class GenericNotification(BaseModel):
    method: str
    params: dict[str, object] = Field(default_factory=dict)


class GenericServerRequest(BaseModel):
    id: str | int
    method: str
    params: dict[str, object] = Field(default_factory=dict)
