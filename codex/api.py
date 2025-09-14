from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from .config import CodexConfig
from .event import AnyEventMsg, Event
from .native import run_exec_collect as native_run_exec_collect
from .native import start_exec_stream as native_start_exec_stream


class CodexError(Exception):
    """Base exception for codex-python."""


class CodexNativeError(CodexError):
    """Raised when the native extension is not available or fails."""

    def __init__(self) -> None:
        super().__init__(
            "codex_native extension not installed or failed to run. "
            "Run `make dev-native` or ensure native wheels are installed."
        )


@dataclass(slots=True)
class Conversation:
    """A stateful conversation with Codex, streaming events natively."""

    _stream: Iterable[dict]

    def __iter__(self) -> Iterator[Event]:
        """Yield `Event` objects from the native stream."""
        for item in self._stream:
            try:
                yield Event.model_validate(item)
            except Exception:
                ev_id = item.get("id") if isinstance(item, dict) else None
                msg_obj = item.get("msg") if isinstance(item, dict) else None
                if isinstance(msg_obj, dict) and isinstance(msg_obj.get("type"), str):
                    yield Event(id=ev_id or "unknown", msg=AnyEventMsg(**msg_obj))
                else:
                    yield Event(id=ev_id or "unknown", msg=AnyEventMsg(type="unknown"))


@dataclass(slots=True)
class CodexClient:
    """Lightweight, synchronous client for the native Codex core.

    Provides defaults for repeated invocations and conversation management.
    """

    config: CodexConfig | None = None
    load_default_config: bool = True
    env: Mapping[str, str] | None = None
    extra_args: Sequence[str] | None = None

    def start_conversation(
        self,
        prompt: str,
        *,
        config: CodexConfig | None = None,
        load_default_config: bool | None = None,
    ) -> Conversation:
        """Start a new conversation and return a streaming iterator over events."""
        eff_config = config if config is not None else self.config
        eff_load_default_config = (
            load_default_config if load_default_config is not None else self.load_default_config
        )

        try:
            stream = native_start_exec_stream(
                prompt,
                config_overrides=eff_config.to_dict() if eff_config else None,
                load_default_config=eff_load_default_config,
            )
            return Conversation(_stream=stream)
        except RuntimeError as e:
            raise CodexNativeError() from e


def run_exec(
    prompt: str,
    *,
    config: CodexConfig | None = None,
    load_default_config: bool = True,
) -> list[Event]:
    """
    Run a prompt through the native Codex engine and return a list of events.

    - Raises CodexNativeError if the native extension is unavailable or fails.
    """
    try:
        events = native_run_exec_collect(
            prompt,
            config_overrides=config.to_dict() if config else None,
            load_default_config=load_default_config,
        )
    except RuntimeError as e:
        raise CodexNativeError() from e

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
