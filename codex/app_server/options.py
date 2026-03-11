"""Options for connecting to and using `codex app-server`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from codex._config_types import CodexConfigObject
from codex.output_schema import OutputSchemaInput, normalize_output_schema
from codex.protocol import types as protocol


class _AppServerOptionsModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        frozen=True,
        extra="forbid",
    )

    def _to_payload(self) -> dict[str, object]:
        return self.model_dump(mode="python", by_alias=True, exclude_none=True)


def _validate_params(model: type[BaseModel], payload: dict[str, object]) -> BaseModel:
    return model.model_validate(payload)


class AppServerClientInfo(_AppServerOptionsModel):
    """Identity metadata sent during the app-server `initialize` handshake."""

    name: str
    version: str
    title: str | None = None


class AppServerInitializeOptions(_AppServerOptionsModel):
    """Handshake options for a single app-server connection."""

    client_info: AppServerClientInfo = Field(
        default_factory=lambda: AppServerClientInfo(
            name="codex_python",
            title="codex-python",
            version="dev",
        )
    )
    experimental_api: bool = False
    opt_out_notification_methods: tuple[str, ...] = ()
    strict_protocol: bool = Field(default=False, exclude=True)

    def to_params(self) -> dict[str, object]:
        """Build the JSON-RPC `initialize` params object."""
        params: dict[str, object] = {
            "clientInfo": self.client_info.model_dump(
                mode="python",
                by_alias=True,
                exclude_none=True,
            )
        }
        capabilities: dict[str, object] = {}
        if self.experimental_api:
            capabilities["experimentalApi"] = True
        if self.opt_out_notification_methods:
            capabilities["optOutNotificationMethods"] = list(self.opt_out_notification_methods)
        if capabilities:
            params["capabilities"] = capabilities
        return params


class AppServerProcessOptions(_AppServerOptionsModel):
    """Process launch options for stdio-based app-server connections."""

    codex_path_override: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    config: CodexConfigObject | None = None
    env: dict[str, str] | None = None
    analytics_default_enabled: bool = False


class AppServerWebSocketOptions(_AppServerOptionsModel):
    """Connection options for websocket-based app-server sessions.

    Conflicting caller inputs raise `ValueError` here before any transport is
    created. This is the public misconfiguration boundary for websocket setup.
    Authentication must go through `bearer_token`; raw `Authorization` headers
    are rejected so validation stays centralized.
    """

    bearer_token: str | None = None
    headers: Mapping[str, str] | None = None
    subprotocols: tuple[str, ...] = ()
    open_timeout: float | None = None
    close_timeout: float | None = None

    def to_connect_kwargs(self) -> dict[str, object]:
        headers = {} if self.headers is None else dict(self.headers)
        if any(name.lower() == "authorization" for name in headers):
            raise ValueError(
                "AppServerWebSocketOptions.headers cannot include Authorization; "
                "use bearer_token instead"
            )
        if self.bearer_token is not None:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        kwargs: dict[str, object] = {}
        if headers:
            kwargs["additional_headers"] = headers
        if self.subprotocols:
            kwargs["subprotocols"] = list(self.subprotocols)
        if self.open_timeout is not None:
            kwargs["open_timeout"] = self.open_timeout
        if self.close_timeout is not None:
            kwargs["close_timeout"] = self.close_timeout
        return kwargs


class AppServerTurnOptions(_AppServerOptionsModel):
    """High-level options for starting a turn on an app-server thread.

    Protocol-owned override fields use generated protocol types directly so the
    public surface matches the JSON-RPC contract instead of accepting arbitrary
    strings and deferring failures to the transport boundary.
    """

    approval_policy: protocol.AskForApproval | None = None
    collaboration_mode: protocol.CollaborationMode | None = None
    cwd: str | None = None
    effort: protocol.ReasoningEffort | None = None
    model: str | None = None
    output_schema: OutputSchemaInput | None = None
    personality: protocol.Personality | None = None
    sandbox_policy: protocol.SandboxPolicy | None = None
    service_tier: protocol.ServiceTier | None = None
    summary: protocol.ReasoningSummary | None = None

    @field_serializer("output_schema", when_used="unless-none")
    def _serialize_output_schema(self, value: OutputSchemaInput) -> object:
        return normalize_output_schema(value)

    def to_params(self, *, thread_id: str, input: Sequence[object]) -> protocol.TurnStartParams:
        payload: dict[str, object] = self.model_dump(
            mode="python", by_alias=True, exclude_none=True
        )
        payload["input"] = input
        payload["threadId"] = thread_id
        return protocol.TurnStartParams.model_validate(payload)


class AppServerThreadStartOptions(_AppServerOptionsModel):
    """High-level options for creating a new app-server thread."""

    approval_policy: protocol.AskForApproval | None = None
    base_instructions: str | None = None
    config: CodexConfigObject | None = None
    cwd: str | None = None
    developer_instructions: str | None = None
    dynamic_tools: list[protocol.DynamicToolSpec] | None = None
    ephemeral: bool | None = None
    experimental_raw_events: bool | None = None
    mock_experimental_field: str | None = None
    model: str | None = None
    model_provider: str | None = None
    persist_extended_history: bool | None = None
    personality: protocol.Personality | None = None
    sandbox: protocol.SandboxMode | None = None
    service_name: str | None = None
    service_tier: protocol.ServiceTier | None = None

    def to_params(self) -> protocol.ThreadStartParams:
        return cast(
            protocol.ThreadStartParams,
            _validate_params(protocol.ThreadStartParams, self._to_payload()),
        )


class AppServerThreadResumeOptions(_AppServerOptionsModel):
    """High-level options for resuming an existing app-server thread."""

    approval_policy: protocol.AskForApproval | None = None
    base_instructions: str | None = None
    config: CodexConfigObject | None = None
    cwd: str | None = None
    developer_instructions: str | None = None
    history: list[protocol.ResponseItem] | None = None
    model: str | None = None
    model_provider: str | None = None
    path: str | None = None
    persist_extended_history: bool | None = None
    personality: protocol.Personality | None = None
    sandbox: protocol.SandboxMode | None = None
    service_tier: protocol.ServiceTier | None = None

    def to_params(self, *, thread_id: str) -> protocol.ThreadResumeParams:
        payload = self._to_payload()
        payload["threadId"] = thread_id
        return cast(
            protocol.ThreadResumeParams,
            _validate_params(protocol.ThreadResumeParams, payload),
        )


class AppServerThreadForkOptions(_AppServerOptionsModel):
    """High-level options for forking an app-server thread."""

    approval_policy: protocol.AskForApproval | None = None
    base_instructions: str | None = None
    config: CodexConfigObject | None = None
    cwd: str | None = None
    developer_instructions: str | None = None
    model: str | None = None
    model_provider: str | None = None
    path: str | None = None
    persist_extended_history: bool | None = None
    sandbox: protocol.SandboxMode | None = None
    service_tier: protocol.ServiceTier | None = None

    def to_params(self, *, thread_id: str) -> protocol.ThreadForkParams:
        payload = self._to_payload()
        payload["threadId"] = thread_id
        return cast(
            protocol.ThreadForkParams,
            _validate_params(protocol.ThreadForkParams, payload),
        )


class AppServerThreadListOptions(_AppServerOptionsModel):
    """High-level filters for listing stored app-server threads."""

    archived: bool | None = None
    cursor: str | None = None
    cwd: str | None = None
    limit: int | None = None
    model_providers: list[str] | None = None
    search_term: str | None = None
    sort_key: protocol.ThreadSortKey | None = None
    source_kinds: list[protocol.ThreadSourceKind] | None = None

    def to_params(self) -> protocol.ThreadListParams:
        return cast(
            protocol.ThreadListParams,
            _validate_params(protocol.ThreadListParams, self._to_payload()),
        )
