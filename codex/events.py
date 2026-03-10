"""Typed exec-event re-exports backed by generated protocol models."""

from __future__ import annotations

from pydantic import BaseModel

from codex.protocol import types as protocol

ExecEvent = BaseModel
SessionConfiguredEvent = protocol.SessionConfiguredEventMsg
TaskStartedEvent = protocol.TaskStartedEventMsg
TaskCompletedEvent = protocol.TaskCompleteEventMsg
AgentMessageEvent = protocol.AgentMessageEventMsg
AgentMessageDeltaEvent = protocol.AgentMessageDeltaEventMsg
TokenCountEvent = protocol.TokenCountEventMsg
ItemStartedEvent = protocol.ItemStartedEventMsg
ItemCompletedEvent = protocol.ItemCompletedEventMsg
ErrorEvent = protocol.ErrorEventMsg
StreamErrorEvent = protocol.StreamErrorEventMsg
TurnAbortedEvent = protocol.TurnAbortedEventMsg

__all__ = [
    "ExecEvent",
    "SessionConfiguredEvent",
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "AgentMessageEvent",
    "AgentMessageDeltaEvent",
    "TokenCountEvent",
    "ItemStartedEvent",
    "ItemCompletedEvent",
    "ErrorEvent",
    "StreamErrorEvent",
    "TurnAbortedEvent",
]
