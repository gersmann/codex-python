from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any, Literal

from .config import (
    ApprovalPolicy,
    CodexConfig,
    ReasoningEffort,
    ReasoningSummary,
    SandboxMode,
)
from .event import AnyEventMsg, Event
from .protocol.types import ReviewDecision as ReviewDecisionProto


class CodexError(Exception):
    """Base exception for codex-python."""


class CodexNativeError(CodexError):
    """Raised when the native extension is not available or fails."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or (
                "codex_native extension not installed or failed to run. "
                "Run `make dev-native` or ensure native wheels are installed."
            )
        )


# Narrow string unions so callers get full type checking without accepting arbitrary str.
type ApprovalPolicyLike = (
    ApprovalPolicy
    | Literal[
        "untrusted",
        "on-failure",
        "on-request",
        "never",
    ]
)
type SandboxModeLike = (
    SandboxMode
    | Literal[
        "read-only",
        "workspace-write",
        "danger-full-access",
    ]
)
type ReasoningEffortLike = (
    ReasoningEffort
    | Literal[
        "minimal",
        "low",
        "medium",
        "high",
    ]
)
type ReasoningSummaryLike = (
    ReasoningSummary
    | Literal[
        "auto",
        "concise",
        "detailed",
        "none",
    ]
)
type ReviewDecisionLike = (
    ReviewDecisionProto
    | Literal[
        "approved",
        "approved_for_session",
        "denied",
        "abort",
    ]
)


def _enum_to_str(value: Any) -> str | None:
    if value is None:
        return None
    v = getattr(value, "value", None)
    if isinstance(v, str):
        return v
    if isinstance(value, str):
        return value
    raise TypeError(f"expected enum or str, got {type(value).__name__}")


class Conversation:
    """Stateful conversation backed by the native core."""

    def __init__(self, _native: Any) -> None:
        self._native = _native

    def __iter__(self) -> Iterator[Event]:
        iterator = iter(self._native)
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                return
            except RuntimeError as exc:
                raise CodexNativeError(str(exc)) from exc
            try:
                yield Event.model_validate(item)
            except Exception:
                ev_id = item.get("id") if isinstance(item, dict) else None
                msg_obj = item.get("msg") if isinstance(item, dict) else None
                if isinstance(msg_obj, dict) and isinstance(msg_obj.get("type"), str):
                    yield Event(id=ev_id or "unknown", msg=AnyEventMsg(**msg_obj))
                else:
                    yield Event(id=ev_id or "unknown", msg=AnyEventMsg(type="unknown"))

    def submit_user_turn(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        approval_policy: ApprovalPolicyLike | None = None,
        sandbox_mode: SandboxModeLike | None = None,
        model: str | None = None,
        effort: ReasoningEffortLike | None = None,
        summary: ReasoningSummaryLike | None = None,
        output_schema: Any | None = None,
    ) -> None:
        try:
            self._native.submit_user_turn(
                prompt,
                cwd=cwd,
                approval_policy=_enum_to_str(approval_policy),
                sandbox_mode=_enum_to_str(sandbox_mode),
                model=model,
                effort=_enum_to_str(effort),
                summary=_enum_to_str(summary),
                output_schema=output_schema,
            )
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def submit_review(self, prompt: str, user_facing_hint: str | None = None) -> None:
        try:
            self._native.submit_review(prompt, user_facing_hint)
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def approve_exec(self, id: str, decision: ReviewDecisionLike) -> None:
        try:
            self._native.approve_exec(id, _enum_to_str(decision))
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def approve_patch(self, id: str, decision: ReviewDecisionLike) -> None:
        try:
            self._native.approve_patch(id, _enum_to_str(decision))
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def interrupt(self) -> None:
        try:
            self._native.interrupt()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def shutdown(self) -> None:
        try:
            self._native.shutdown()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    # Extras mirroring native
    def user_input_text(self, text: str) -> None:
        try:
            self._native.user_input_text(text)
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def override_turn_context(
        self,
        *,
        cwd: str | None = None,
        approval_policy: ApprovalPolicyLike | None = None,
        sandbox_mode: SandboxModeLike | None = None,
        model: str | None = None,
        effort: ReasoningEffortLike | None = None,
        clear_effort: bool = False,
        summary: ReasoningSummaryLike | None = None,
    ) -> None:
        try:
            self._native.override_turn_context(
                cwd,
                _enum_to_str(approval_policy),
                _enum_to_str(sandbox_mode),
                model,
                _enum_to_str(effort),
                clear_effort,
                _enum_to_str(summary),
            )
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def add_to_history(self, text: str) -> None:
        try:
            self._native.add_to_history(text)
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def get_history_entry(self, log_id: int, offset: int) -> None:
        try:
            self._native.get_history_entry(log_id, offset)
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def get_path(self) -> None:
        try:
            self._native.get_path()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def list_mcp_tools(self) -> None:
        try:
            self._native.list_mcp_tools()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def list_custom_prompts(self) -> None:
        try:
            self._native.list_custom_prompts()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e

    def compact(self) -> None:
        try:
            self._native.compact()
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e


class CodexClient:
    def __init__(
        self, *, config: CodexConfig | None = None, load_default_config: bool = True
    ) -> None:
        self.config = config
        self.load_default_config = load_default_config

    def start_conversation(
        self,
        *,
        config: CodexConfig | None = None,
        load_default_config: bool | None = None,
    ) -> Conversation:
        eff_config = config if config is not None else self.config
        eff_load = (
            load_default_config if load_default_config is not None else self.load_default_config
        )
        try:
            from .native import start_conversation as _start

            native = _start(
                config_overrides=eff_config.to_dict() if eff_config else None,
                load_default_config=eff_load,
            )
        except RuntimeError as e:
            raise CodexNativeError(str(e)) from e
        return Conversation(native)

    async def astart_conversation(
        self,
        *,
        config: CodexConfig | None = None,
        load_default_config: bool | None = None,
    ) -> AsyncConversation:
        eff_config = config if config is not None else self.config
        eff_load = (
            load_default_config if load_default_config is not None else self.load_default_config
        )

        def _call() -> Any:
            from .native import start_conversation as _start

            return _start(
                config_overrides=eff_config.to_dict() if eff_config else None,
                load_default_config=eff_load,
            )

        native = await asyncio.to_thread(_call)
        return AsyncConversation(Conversation(native))


class AsyncConversation:
    def __init__(self, conv: Conversation) -> None:
        self._conv = conv
        self._native_iter = iter(self._conv._native)

    def __aiter__(self) -> AsyncConversation:
        return self

    async def __anext__(self) -> Event:
        def _next(it: Any) -> tuple[Any | None, bool]:
            try:
                return next(it), True
            except StopIteration:
                return None, False

        item, ok = await asyncio.to_thread(_next, self._native_iter)
        if not ok:
            raise StopAsyncIteration
        try:
            from typing import cast as _cast

            return _cast(Event, Event.model_validate(item))
        except Exception:
            ev_id = item.get("id") if isinstance(item, dict) else None
            msg_obj = item.get("msg") if isinstance(item, dict) else None
            if isinstance(msg_obj, dict) and isinstance(msg_obj.get("type"), str):
                return Event(id=ev_id or "unknown", msg=AnyEventMsg(**msg_obj))
            return Event(id=ev_id or "unknown", msg=AnyEventMsg(type="unknown"))

    async def submit_user_turn(
        self,
        prompt: str,
        *,
        cwd: str | None = None,
        approval_policy: ApprovalPolicyLike | None = None,
        sandbox_mode: SandboxModeLike | None = None,
        model: str | None = None,
        effort: ReasoningEffortLike | None = None,
        summary: ReasoningSummaryLike | None = None,
        output_schema: Any | None = None,
    ) -> None:
        ap: ApprovalPolicyLike | None = approval_policy
        sm: SandboxModeLike | None = sandbox_mode
        ef: ReasoningEffortLike | None = effort
        su: ReasoningSummaryLike | None = summary
        await asyncio.to_thread(
            self._conv.submit_user_turn,
            prompt,
            cwd=cwd,
            approval_policy=ap,
            sandbox_mode=sm,
            model=model,
            effort=ef,
            summary=su,
            output_schema=output_schema,
        )

    async def submit_review(self, prompt: str, user_facing_hint: str | None = None) -> None:
        await asyncio.to_thread(self._conv.submit_review, prompt, user_facing_hint)

    async def approve_exec(self, id: str, decision: ReviewDecisionLike) -> None:
        await asyncio.to_thread(self._conv.approve_exec, id, decision)

    async def approve_patch(self, id: str, decision: ReviewDecisionLike) -> None:
        await asyncio.to_thread(self._conv.approve_patch, id, decision)

    async def interrupt(self) -> None:
        await asyncio.to_thread(self._conv.interrupt)

    async def shutdown(self) -> None:
        await asyncio.to_thread(self._conv.shutdown)

    async def user_input_text(self, text: str) -> None:
        await asyncio.to_thread(self._conv.user_input_text, text)

    async def override_turn_context(
        self,
        *,
        cwd: str | None = None,
        approval_policy: ApprovalPolicyLike | None = None,
        sandbox_mode: SandboxModeLike | None = None,
        model: str | None = None,
        effort: ReasoningEffortLike | None = None,
        clear_effort: bool = False,
        summary: ReasoningSummaryLike | None = None,
    ) -> None:
        ap: ApprovalPolicyLike | None = approval_policy
        sm: SandboxModeLike | None = sandbox_mode
        ef: ReasoningEffortLike | None = effort
        su: ReasoningSummaryLike | None = summary
        await asyncio.to_thread(
            self._conv.override_turn_context,
            cwd=cwd,
            approval_policy=ap,
            sandbox_mode=sm,
            model=model,
            effort=ef,
            clear_effort=clear_effort,
            summary=su,
        )

    async def add_to_history(self, text: str) -> None:
        await asyncio.to_thread(self._conv.add_to_history, text)

    async def get_history_entry(self, log_id: int, offset: int) -> None:
        await asyncio.to_thread(self._conv.get_history_entry, log_id, offset)

    async def get_path(self) -> None:
        await asyncio.to_thread(self._conv.get_path)

    async def list_mcp_tools(self) -> None:
        await asyncio.to_thread(self._conv.list_mcp_tools)

    async def list_custom_prompts(self) -> None:
        await asyncio.to_thread(self._conv.list_custom_prompts)

    async def compact(self) -> None:
        await asyncio.to_thread(self._conv.compact)
