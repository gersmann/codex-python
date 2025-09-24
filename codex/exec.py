from __future__ import annotations

from typing import Any

from .client import CodexError, CodexNativeError
from .config import CodexConfig
from .event import AnyEventMsg, Event
from .native import run_exec_collect as native_run_exec_collect
from .native import run_review_collect as native_run_review_collect
from .protocol.types import EventMsgTaskComplete


def run_exec(
    prompt: str,
    *,
    config: CodexConfig | None = None,
    load_default_config: bool = True,
    output_schema: Any | None = None,
) -> list[Event]:
    try:
        events = native_run_exec_collect(
            prompt,
            config_overrides=config.to_dict() if config else None,
            load_default_config=load_default_config,
            output_schema=output_schema,
        )
    except RuntimeError as e:
        raise CodexNativeError(str(e)) from e

    out: list[Event] = []
    for item in events:
        try:
            out.append(Event.model_validate(item))
        except Exception:
            ev_id = item.get("id") if isinstance(item, dict) else None
            msg_obj = item.get("msg") if isinstance(item, dict) else None
            if isinstance(msg_obj, dict) and isinstance(msg_obj.get("type"), str):
                out.append(Event(id=ev_id or "unknown", msg=AnyEventMsg(**msg_obj)))
            else:
                out.append(Event(id=ev_id or "unknown", msg=AnyEventMsg(type="unknown")))
    return out


def run_review(
    prompt: str,
    *,
    user_facing_hint: str | None = None,
    config: CodexConfig | None = None,
    load_default_config: bool = True,
) -> list[Event]:
    try:
        events = native_run_review_collect(
            prompt,
            user_facing_hint=user_facing_hint,
            config_overrides=config.to_dict() if config else None,
            load_default_config=load_default_config,
        )
    except RuntimeError as e:
        raise CodexNativeError(str(e)) from e

    out: list[Event] = []
    for item in events:
        try:
            out.append(Event.model_validate(item))
        except Exception:
            ev_id = item.get("id") if isinstance(item, dict) else None
            msg_obj = item.get("msg") if isinstance(item, dict) else None
            if isinstance(msg_obj, dict) and isinstance(msg_obj.get("type"), str):
                out.append(Event(id=ev_id or "unknown", msg=AnyEventMsg(**msg_obj)))
            else:
                out.append(Event(id=ev_id or "unknown", msg=AnyEventMsg(type="unknown")))
    return out


def run_prompt(
    prompt: str,
    *,
    config: CodexConfig | None = None,
    load_default_config: bool = True,
    output_schema: Any | None = None,
) -> Any:
    events = run_exec(
        prompt,
        config=config,
        load_default_config=load_default_config,
        output_schema=output_schema,
    )

    last: str | None = None
    for ev in reversed(events):
        try:
            if isinstance(ev.msg, EventMsgTaskComplete):
                last = ev.msg.last_agent_message
                break
        except Exception:
            pass
        msg_obj: Any
        if hasattr(ev.msg, "model_dump"):
            msg_obj = ev.msg.model_dump()
        elif isinstance(ev.msg, dict):
            msg_obj = ev.msg
        else:
            msg_obj = {}
        if msg_obj.get("type") == "task_complete":
            last = msg_obj.get("last_agent_message")
            break

    last = last or ""
    if output_schema is None:
        return last

    import json

    def try_parse(s: str) -> Any:
        return json.loads(s)

    try:
        return try_parse(last)
    except Exception:
        pass

    first_obj, last_obj = last.find("{"), last.rfind("}")
    first_arr, last_arr = last.find("["), last.rfind("]")
    candidates: list[str] = []
    if 0 <= first_obj < last_obj:
        candidates.append(last[first_obj : last_obj + 1])
    if 0 <= first_arr < last_arr:
        candidates.append(last[first_arr : last_arr + 1])

    for cand in candidates:
        try:
            return try_parse(cand)
        except Exception:
            continue

    raise CodexError(
        "Failed to parse structured output as JSON; last assistant message did not contain valid JSON."
    )
