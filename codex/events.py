from __future__ import annotations

from typing import Literal, TypedDict

from codex.items import ThreadItem


class ThreadStartedEvent(TypedDict):
    type: Literal["thread.started"]
    thread_id: str


class TurnStartedEvent(TypedDict):
    type: Literal["turn.started"]


class Usage(TypedDict):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class TurnCompletedEvent(TypedDict):
    type: Literal["turn.completed"]
    usage: Usage


class ThreadError(TypedDict):
    message: str


class TurnFailedEvent(TypedDict):
    type: Literal["turn.failed"]
    error: ThreadError


class ItemStartedEvent(TypedDict):
    type: Literal["item.started"]
    item: ThreadItem


class ItemUpdatedEvent(TypedDict):
    type: Literal["item.updated"]
    item: ThreadItem


class ItemCompletedEvent(TypedDict):
    type: Literal["item.completed"]
    item: ThreadItem


class ThreadErrorEvent(TypedDict):
    type: Literal["error"]
    message: str


ThreadEvent = (
    ThreadStartedEvent
    | TurnStartedEvent
    | TurnCompletedEvent
    | TurnFailedEvent
    | ItemStartedEvent
    | ItemUpdatedEvent
    | ItemCompletedEvent
    | ThreadErrorEvent
)
