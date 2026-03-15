"""Options for connecting to and using `codex app-server`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from codex._config_types import CodexConfig
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

    name: str = Field(description="Sent as initialize.params.clientInfo.name.")
    version: str = Field(description="Sent as initialize.params.clientInfo.version.")
    title: str | None = Field(
        default=None,
        description="Sent as initialize.params.clientInfo.title.",
    )


class AppServerInitializeOptions(_AppServerOptionsModel):
    """Handshake options for a single app-server connection."""

    client_info: AppServerClientInfo = Field(
        default_factory=lambda: AppServerClientInfo(
            name="codex_python",
            title="codex-python",
            version="dev",
        ),
        description="Metadata sent in initialize.params.clientInfo.",
    )
    experimental_api: bool = Field(
        default=False,
        description=(
            "Sent as initialize.params.capabilities.experimentalApi. "
            "Opts the connection into experimental app-server methods and fields."
        ),
    )
    opt_out_notification_methods: tuple[str, ...] = Field(
        default=(),
        description=(
            "Sent as initialize.params.capabilities.optOutNotificationMethods. "
            "Exact notification method names to suppress for this connection."
        ),
    )
    strict_protocol: bool = Field(
        default=False,
        exclude=True,
        description=(
            "SDK-only parsing mode. Not sent on the wire. "
            "When false, unknown protocol messages can fall back to generic models."
        ),
    )

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

    codex_path_override: str | None = Field(
        default=None,
        description="Override the codex binary path used for the stdio subprocess.",
    )
    base_url: str | None = Field(
        default=None,
        description="Inject the upstream base URL for the child app-server process.",
    )
    api_key: str | None = Field(
        default=None,
        description="Inject the API key for the child app-server process.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Launch-time Codex config overrides for the child process.",
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Additional environment variables merged into the child process environment.",
    )
    analytics_default_enabled: bool = Field(
        default=False,
        description="Default analytics setting for the spawned local process.",
    )


class AppServerWebSocketOptions(_AppServerOptionsModel):
    """Connection options for websocket-based app-server sessions.

    Conflicting caller inputs raise `ValueError` here before any transport is
    created. This is the public misconfiguration boundary for websocket setup.
    Authentication must go through `bearer_token`; raw `Authorization` headers
    are rejected so validation stays centralized.
    """

    bearer_token: str | None = Field(
        default=None,
        description="Adds an Authorization: Bearer header to the websocket handshake.",
    )
    headers: Mapping[str, str] | None = Field(
        default=None,
        description=(
            "Extra websocket handshake headers. Authorization is rejected here; "
            "use bearer_token instead."
        ),
    )
    subprotocols: tuple[str, ...] = Field(
        default=(),
        description="Websocket subprotocols offered during connection setup.",
    )
    open_timeout: float | None = Field(
        default=None,
        description="Timeout used while opening the websocket connection.",
    )
    close_timeout: float | None = Field(
        default=None,
        description="Timeout used while closing the websocket connection.",
    )

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

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Sent as turn/start approvalPolicy.",
    )
    collaboration_mode: protocol.CollaborationMode | None = Field(
        default=None,
        description="Sent as turn/start collaborationMode.",
    )
    cwd: str | None = Field(
        default=None,
        description="Sent as turn/start cwd.",
    )
    effort: protocol.ReasoningEffort | None = Field(
        default=None,
        description="Sent as turn/start effort.",
    )
    model: str | None = Field(
        default=None,
        description="Sent as turn/start model.",
    )
    output_schema: OutputSchemaInput | None = Field(
        default=None,
        description=(
            "Sent as turn/start outputSchema after SDK normalization. "
            "Accepts raw JSON Schema or a Pydantic model class."
        ),
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Sent as turn/start personality.",
    )
    sandbox_policy: protocol.SandboxPolicy | None = Field(
        default=None,
        description="Sent as turn/start sandboxPolicy.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Sent as turn/start serviceTier.",
    )
    summary: protocol.ReasoningSummary | None = Field(
        default=None,
        description="Sent as turn/start summary.",
    )

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

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Sent as thread/start approvalPolicy.",
    )
    base_instructions: str | None = Field(
        default=None,
        description="Sent as thread/start baseInstructions.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Sent as thread/start config. Accepts the typed CodexConfig model or a plain dict.",
    )
    cwd: str | None = Field(
        default=None,
        description="Sent as thread/start cwd.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Sent as thread/start developerInstructions.",
    )
    dynamic_tools: list[protocol.DynamicToolSpec] | None = Field(
        default=None,
        description="Sent as thread/start dynamicTools. The public app-server docs mark this as experimental.",
    )
    ephemeral: bool | None = Field(
        default=None,
        description="Sent as thread/start ephemeral.",
    )
    experimental_raw_events: bool | None = Field(
        default=None,
        description=(
            "Sent as thread/start experimentalRawEvents. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    mock_experimental_field: str | None = Field(
        default=None,
        description=(
            "Sent as thread/start mockExperimentalField. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    model: str | None = Field(
        default=None,
        description="Sent as thread/start model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Sent as thread/start modelProvider.",
    )
    persist_extended_history: bool | None = Field(
        default=None,
        description=(
            "Sent as thread/start persistExtendedHistory. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Sent as thread/start personality.",
    )
    sandbox: protocol.SandboxMode | None = Field(
        default=None,
        description="Sent as thread/start sandbox.",
    )
    service_name: str | None = Field(
        default=None,
        description=(
            "Sent as thread/start serviceName. "
            "The public app-server docs describe this as an optional service label for thread-level metrics."
        ),
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Sent as thread/start serviceTier.",
    )

    def to_params(self) -> protocol.ThreadStartParams:
        return cast(
            protocol.ThreadStartParams,
            _validate_params(protocol.ThreadStartParams, self._to_payload()),
        )


class AppServerThreadResumeOptions(_AppServerOptionsModel):
    """High-level options for resuming an existing app-server thread."""

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Sent as thread/resume approvalPolicy.",
    )
    base_instructions: str | None = Field(
        default=None,
        description="Sent as thread/resume baseInstructions.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Sent as thread/resume config. Accepts the typed CodexConfig model or a plain dict.",
    )
    cwd: str | None = Field(
        default=None,
        description="Sent as thread/resume cwd.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Sent as thread/resume developerInstructions.",
    )
    history: list[protocol.ResponseItem] | None = Field(
        default=None,
        description="Sent as thread/resume history.",
    )
    model: str | None = Field(
        default=None,
        description="Sent as thread/resume model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Sent as thread/resume modelProvider.",
    )
    path: str | None = Field(
        default=None,
        description="Sent as thread/resume path.",
    )
    persist_extended_history: bool | None = Field(
        default=None,
        description=(
            "Sent as thread/resume persistExtendedHistory. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    personality: protocol.Personality | None = Field(
        default=None,
        description="Sent as thread/resume personality.",
    )
    sandbox: protocol.SandboxMode | None = Field(
        default=None,
        description="Sent as thread/resume sandbox.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Sent as thread/resume serviceTier.",
    )

    def to_params(self, *, thread_id: str) -> protocol.ThreadResumeParams:
        payload = self._to_payload()
        payload["threadId"] = thread_id
        return cast(
            protocol.ThreadResumeParams,
            _validate_params(protocol.ThreadResumeParams, payload),
        )


class AppServerThreadForkOptions(_AppServerOptionsModel):
    """High-level options for forking an app-server thread."""

    approval_policy: protocol.AskForApproval | None = Field(
        default=None,
        description="Sent as thread/fork approvalPolicy.",
    )
    base_instructions: str | None = Field(
        default=None,
        description="Sent as thread/fork baseInstructions.",
    )
    config: CodexConfig | None = Field(
        default=None,
        description="Sent as thread/fork config. Accepts the typed CodexConfig model or a plain dict.",
    )
    cwd: str | None = Field(
        default=None,
        description="Sent as thread/fork cwd.",
    )
    developer_instructions: str | None = Field(
        default=None,
        description="Sent as thread/fork developerInstructions.",
    )
    model: str | None = Field(
        default=None,
        description="Sent as thread/fork model.",
    )
    model_provider: str | None = Field(
        default=None,
        description="Sent as thread/fork modelProvider.",
    )
    path: str | None = Field(
        default=None,
        description="Sent as thread/fork path.",
    )
    persist_extended_history: bool | None = Field(
        default=None,
        description=(
            "Sent as thread/fork persistExtendedHistory. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    sandbox: protocol.SandboxMode | None = Field(
        default=None,
        description="Sent as thread/fork sandbox.",
    )
    service_tier: protocol.ServiceTier | None = Field(
        default=None,
        description="Sent as thread/fork serviceTier.",
    )

    def to_params(self, *, thread_id: str) -> protocol.ThreadForkParams:
        payload = self._to_payload()
        payload["threadId"] = thread_id
        return cast(
            protocol.ThreadForkParams,
            _validate_params(protocol.ThreadForkParams, payload),
        )


class AppServerThreadListOptions(_AppServerOptionsModel):
    """High-level filters for listing stored app-server threads."""

    archived: bool | None = Field(
        default=None,
        description="Sent as thread/list archived.",
    )
    cursor: str | None = Field(
        default=None,
        description="Sent as thread/list cursor.",
    )
    cwd: str | None = Field(
        default=None,
        description="Sent as thread/list cwd.",
    )
    limit: int | None = Field(
        default=None,
        description="Sent as thread/list limit.",
    )
    model_providers: list[str] | None = Field(
        default=None,
        description="Sent as thread/list modelProviders.",
    )
    search_term: str | None = Field(
        default=None,
        description=(
            "Sent as thread/list searchTerm. "
            "Present in the generated protocol; not described in the public app-server docs."
        ),
    )
    sort_key: protocol.ThreadSortKey | None = Field(
        default=None,
        description="Sent as thread/list sortKey.",
    )
    source_kinds: list[protocol.ThreadSourceKind] | None = Field(
        default=None,
        description="Sent as thread/list sourceKinds.",
    )

    def to_params(self) -> protocol.ThreadListParams:
        return cast(
            protocol.ThreadListParams,
            _validate_params(protocol.ThreadListParams, self._to_payload()),
        )
