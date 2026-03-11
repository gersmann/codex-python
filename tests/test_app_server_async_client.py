from __future__ import annotations

import asyncio

import pytest

from codex.app_server._async_client import AsyncEventsClient, AsyncTurnStream
from codex.app_server.models import ReviewResult
from codex.protocol import types as protocol


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []

    def subscribe_notifications(self, methods: object, *, predicate: object = None) -> object:
        self.calls.append((methods, predicate))
        return "subscription"


class _FakeSubscription:
    def __init__(self) -> None:
        self.updated_predicate: object | None = None
        self.closed = False

    async def next(self) -> protocol.ServerNotification:
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True

    def update_predicate(self, predicate: object) -> None:
        self.updated_predicate = predicate


class _FakeThread:
    def __init__(self) -> None:
        self.id = "thr-1"
        self._client = object()


class _FakeRpc:
    async def request_typed(
        self,
        method: str,
        params: object,
        result_model: type[ReviewResult],
    ) -> ReviewResult:
        _ = (params, result_model)
        assert method == "review/start"
        return ReviewResult.model_validate(
            {
                "turn": _turn_payload(status="inProgress"),
                "reviewThreadId": "thr-review-1",
            }
        )


def _turn_payload(turn_id: str = "turn-1", *, status: str = "completed") -> dict[str, object]:
    return {
        "id": turn_id,
        "status": status,
        "items": [],
        "error": None,
    }


def test_async_events_client_subscribe_delegates_to_session() -> None:
    session = _FakeSession()
    events = AsyncEventsClient(session)  # type: ignore[arg-type]

    subscription = events.subscribe(["turn/completed"])

    assert subscription == "subscription"
    assert session.calls == [(["turn/completed"], None)]


def test_async_turn_stream_scope_predicate_filters_by_thread_and_turn() -> None:
    predicate = AsyncTurnStream._scope_predicate("thr-1", "turn-1")

    matching_turn = protocol.TurnCompletedNotificationModel.model_validate(
        {
            "method": "turn/completed",
            "params": {"threadId": "thr-1", "turn": _turn_payload()},
        }
    )
    matching_usage = protocol.ThreadTokenUsageUpdatedNotificationModel.model_validate(
        {
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-other",
                "tokenUsage": {
                    "last": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                    "total": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                },
            },
        }
    )
    wrong_thread = protocol.TurnCompletedNotificationModel.model_validate(
        {
            "method": "turn/completed",
            "params": {"threadId": "thr-2", "turn": _turn_payload()},
        }
    )

    assert predicate(matching_turn) is True
    assert predicate(matching_usage) is True
    assert predicate(wrong_thread) is False


def test_async_turn_stream_apply_tracks_text_usage_items_and_final_turn() -> None:
    stream = AsyncTurnStream(
        _FakeThread(),  # type: ignore[arg-type]
        _FakeSubscription(),  # type: ignore[arg-type]
        protocol.Turn.model_validate(_turn_payload(status="inProgress")),
    )

    delta = protocol.ItemAgentMessageDeltaNotification.model_validate(
        {
            "method": "item/agentMessage/delta",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "itemId": "item-1",
                "delta": "Hello ",
            },
        }
    )
    usage_notification = protocol.ThreadTokenUsageUpdatedNotificationModel.model_validate(
        {
            "method": "thread/tokenUsage/updated",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "tokenUsage": {
                    "last": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                    "total": {
                        "inputTokens": 1,
                        "cachedInputTokens": 0,
                        "outputTokens": 2,
                        "reasoningOutputTokens": 0,
                        "totalTokens": 3,
                    },
                },
            },
        }
    )
    item_completed = protocol.ItemCompletedNotificationModel.model_validate(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "item": {
                    "id": "item-1",
                    "type": "agentMessage",
                    "text": "Hello world",
                    "phase": "final_answer",
                },
            },
        }
    )
    turn_completed = protocol.TurnCompletedNotificationModel.model_validate(
        {
            "method": "turn/completed",
            "params": {"threadId": "thr-1", "turn": _turn_payload()},
        }
    )

    stream._apply(delta)
    stream._apply(usage_notification)
    stream._apply(item_completed)
    stream._apply(turn_completed)

    assert stream.text_deltas == ("Hello ",)
    assert stream.final_text == "Hello world"
    assert stream.usage is not None
    assert stream.usage.total.totalTokens == 3
    assert len(stream.items) == 1
    assert stream.final_message is not None
    assert stream.final_turn is not None


def test_async_turn_stream_apply_replaces_existing_item_state() -> None:
    stream = AsyncTurnStream(
        _FakeThread(),  # type: ignore[arg-type]
        _FakeSubscription(),  # type: ignore[arg-type]
        protocol.Turn.model_validate(_turn_payload(status="inProgress")),
    )

    first_item = protocol.ItemStartedNotificationModel.model_validate(
        {
            "method": "item/started",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "item": {
                    "id": "item-1",
                    "type": "agentMessage",
                    "text": "Draft",
                    "phase": "commentary",
                },
            },
        }
    )
    completed_item = protocol.ItemCompletedNotificationModel.model_validate(
        {
            "method": "item/completed",
            "params": {
                "threadId": "thr-1",
                "turnId": "turn-1",
                "item": {
                    "id": "item-1",
                    "type": "agentMessage",
                    "text": "Final",
                    "phase": "final_answer",
                },
            },
        }
    )

    stream._apply(first_item)
    stream._apply(completed_item)

    assert len(stream.items) == 1
    with pytest.raises(ValueError, match="No terminal turn is available yet"):
        _ = stream.final_message
    with pytest.raises(ValueError, match="No terminal turn is available yet"):
        _ = stream.final_text


def test_async_turn_stream_wait_returns_immediately_when_done() -> None:
    async def scenario() -> None:
        subscription = _FakeSubscription()
        stream = AsyncTurnStream(
            _FakeThread(),  # type: ignore[arg-type]
            subscription,  # type: ignore[arg-type]
            protocol.Turn.model_validate(_turn_payload(status="inProgress")),
        )
        stream._done = True
        stream.final_turn = protocol.Turn.model_validate(_turn_payload(status="completed"))

        assert await stream.wait() is stream
        assert subscription.closed is True

    asyncio.run(scenario())


def test_async_turn_stream_wait_closes_subscription_after_terminal_notification() -> None:
    class _CompletedSubscription(_FakeSubscription):
        def __init__(self) -> None:
            super().__init__()
            self._notifications = [
                protocol.TurnCompletedNotificationModel.model_validate(
                    {
                        "method": "turn/completed",
                        "params": {"threadId": "thr-1", "turn": _turn_payload()},
                    }
                )
            ]

        async def next(self) -> protocol.ServerNotification:
            if not self._notifications:
                raise StopAsyncIteration
            return self._notifications.pop(0)

    async def scenario() -> None:
        subscription = _CompletedSubscription()
        stream = AsyncTurnStream(
            _FakeThread(),  # type: ignore[arg-type]
            subscription,  # type: ignore[arg-type]
            protocol.Turn.model_validate(_turn_payload(status="inProgress")),
        )

        assert await stream.wait() is stream
        assert subscription.closed is True

    asyncio.run(scenario())


def test_async_turn_stream_wait_raises_when_stream_ends_without_terminal_turn() -> None:
    async def scenario() -> None:
        subscription = _FakeSubscription()
        stream = AsyncTurnStream(
            _FakeThread(),  # type: ignore[arg-type]
            subscription,  # type: ignore[arg-type]
            protocol.Turn.model_validate(_turn_payload(status="inProgress")),
        )

        with pytest.raises(ValueError, match="No terminal turn is available yet"):
            await stream.wait()

        assert subscription.closed is True

    asyncio.run(scenario())


def test_async_turn_stream_raise_for_terminal_status_requires_completion() -> None:
    stream = AsyncTurnStream(
        _FakeThread(),  # type: ignore[arg-type]
        _FakeSubscription(),  # type: ignore[arg-type]
        protocol.Turn.model_validate(_turn_payload(status="inProgress")),
    )

    with pytest.raises(ValueError, match="No terminal turn is available yet"):
        stream.raise_for_terminal_status()


def test_async_turn_stream_final_accessors_require_terminal_turn() -> None:
    stream = AsyncTurnStream(
        _FakeThread(),  # type: ignore[arg-type]
        _FakeSubscription(),  # type: ignore[arg-type]
        protocol.Turn.model_validate(_turn_payload(status="inProgress")),
    )
    stream._apply(
        protocol.ItemCompletedNotificationModel.model_validate(
            {
                "method": "item/completed",
                "params": {
                    "threadId": "thr-1",
                    "turnId": "turn-1",
                    "item": {
                        "id": "item-1",
                        "type": "agentMessage",
                        "text": "Final",
                        "phase": "final_answer",
                    },
                },
            }
        )
    )

    with pytest.raises(ValueError, match="No terminal turn is available yet"):
        _ = stream.final_text
    with pytest.raises(ValueError, match="No terminal turn is available yet"):
        _ = stream.final_message


def test_async_turn_stream_start_review_installs_safe_initial_predicate() -> None:
    async def scenario() -> None:
        session = _FakeSession()
        subscription = _FakeSubscription()

        def subscribe_notifications(
            methods: object, *, predicate: object = None
        ) -> _FakeSubscription:
            session.calls.append((methods, predicate))
            return subscription

        session.subscribe_notifications = subscribe_notifications  # type: ignore[method-assign]

        client = type(
            "_FakeClient",
            (),
            {"_session": session, "rpc": _FakeRpc()},
        )()
        thread = _FakeThread()
        thread._client = client

        stream = await AsyncTurnStream.start_review(thread, {"threadId": "thr-1"})

        initial_predicate = session.calls[0][1]
        assert callable(initial_predicate)
        assert callable(subscription.updated_predicate)

        unrelated = protocol.TurnCompletedNotificationModel.model_validate(
            {
                "method": "turn/completed",
                "params": {"threadId": "thr-other", "turn": _turn_payload()},
            }
        )
        matching = protocol.TurnCompletedNotificationModel.model_validate(
            {
                "method": "turn/completed",
                "params": {"threadId": "thr-review-1", "turn": _turn_payload()},
            }
        )

        assert initial_predicate(unrelated) is False
        assert initial_predicate(matching) is False
        assert subscription.updated_predicate(matching) is True
        assert stream.thread_id == "thr-review-1"

        await stream.close()

    asyncio.run(scenario())
