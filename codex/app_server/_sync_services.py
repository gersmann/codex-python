from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any, Protocol

from codex.app_server._sync_support import _SyncRunner
from codex.app_server.models import (
    AccountCancelLoginResult,
    AccountRateLimitsResult,
    AccountReadResult,
    ApiKeyLoginResult,
    AppListResult,
    ChatGptAuthTokensLoginResult,
    ChatGptLoginResult,
    CommandExecResult,
    ConfigReadResult,
    ConfigRequirementsReadResult,
    ConfigWriteResult,
    EmptyResult,
    ExternalAgentConfigDetectResult,
    FeedbackUploadResult,
    McpServerOauthLoginResult,
    McpServerStatus,
    McpServerStatusListResult,
    ModelInfo,
    ModelListResult,
    SkillsConfigWriteResult,
    SkillsListEntry,
    SkillsListResult,
    WindowsSandboxSetupStartResult,
)
from codex.protocol import types as protocol


class _AsyncModelsClientLike(Protocol):
    async def list(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> list[ModelInfo]: ...

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> ModelListResult: ...


class _AsyncAppsClientLike(Protocol):
    async def list(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> list[protocol.AppInfo]: ...

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> AppListResult: ...


class _AsyncSkillsClientLike(Protocol):
    async def list(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> list[SkillsListEntry]: ...

    async def list_page(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> SkillsListResult: ...

    async def write_config(self, *, path: str, enabled: bool) -> SkillsConfigWriteResult: ...


class _AsyncAccountClientLike(Protocol):
    async def read(self, *, refresh_token: bool | None = None) -> AccountReadResult: ...

    async def login_api_key(self, *, api_key: str) -> ApiKeyLoginResult: ...

    async def login_chatgpt(self) -> ChatGptLoginResult: ...

    async def login_chatgpt_tokens(
        self,
        *,
        access_token: str,
        chatgpt_account_id: str,
        chatgpt_plan_type: protocol.PlanType | None = None,
    ) -> ChatGptAuthTokensLoginResult: ...

    async def cancel_login(self, *, login_id: str) -> AccountCancelLoginResult: ...

    async def logout(self) -> EmptyResult: ...

    async def read_rate_limits(self) -> AccountRateLimitsResult: ...


class _AsyncConfigClientLike(Protocol):
    async def read(
        self,
        *,
        cwd: str | None = None,
        include_layers: bool | None = None,
    ) -> ConfigReadResult: ...

    async def reload_mcp_servers(self) -> EmptyResult: ...

    async def write_value(
        self,
        *,
        key_path: str,
        value: Any,
        merge_strategy: protocol.MergeStrategy,
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult: ...

    async def batch_write(
        self,
        *,
        edits: Sequence[protocol.ConfigEdit],
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult: ...

    async def read_requirements(self) -> ConfigRequirementsReadResult: ...


class _AsyncMcpServersClientLike(Protocol):
    async def oauth_login(
        self,
        *,
        name: str,
        scopes: Sequence[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> McpServerOauthLoginResult: ...

    async def list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> list[McpServerStatus]: ...

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> McpServerStatusListResult: ...


class _AsyncFeedbackClientLike(Protocol):
    async def upload(
        self,
        *,
        classification: str,
        include_logs: bool,
        extra_log_files: Sequence[str] | None = None,
        reason: str | None = None,
        thread_id: str | None = None,
    ) -> FeedbackUploadResult: ...


class _AsyncCommandClientLike(Protocol):
    async def execute(
        self,
        *,
        command: Sequence[str],
        cwd: str | None = None,
        disable_output_cap: bool | None = None,
        disable_timeout: bool | None = None,
        env: Mapping[str, object | None] | None = None,
        output_bytes_cap: int | None = None,
        process_id: str | None = None,
        sandbox_policy: protocol.SandboxPolicy | None = None,
        size: protocol.CommandExecTerminalSize | None = None,
        stream_stdin: bool | None = None,
        stream_stdout_stderr: bool | None = None,
        timeout_ms: int | None = None,
        tty: bool | None = None,
    ) -> CommandExecResult: ...

    async def write_stdin(
        self,
        *,
        process_id: str,
        close_stdin: bool | None = None,
        delta_base64: str | None = None,
    ) -> EmptyResult: ...

    async def resize_terminal(
        self,
        *,
        process_id: str,
        size: protocol.CommandExecTerminalSize,
    ) -> EmptyResult: ...

    async def terminate_process(self, *, process_id: str) -> EmptyResult: ...


class _AsyncExternalAgentConfigClientLike(Protocol):
    async def detect(
        self,
        *,
        cwds: Sequence[str] | None = None,
        include_home: bool | None = None,
    ) -> ExternalAgentConfigDetectResult: ...

    async def import_items(
        self,
        *,
        migration_items: Sequence[protocol.ExternalAgentConfigMigrationItem],
    ) -> EmptyResult: ...


class _AsyncWindowsSandboxClientLike(Protocol):
    async def setup_start(
        self,
        *,
        mode: protocol.WindowsSandboxSetupMode,
        cwd: str | None = None,
    ) -> WindowsSandboxSetupStartResult: ...


class _ModelsClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncModelsClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def list(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> list[ModelInfo]:
        return self._run(
            self._async_client.list(
                cursor=cursor,
                include_hidden=include_hidden,
                limit=limit,
            )
        )

    def list_page(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> ModelListResult:
        return self._run(
            self._async_client.list_page(
                cursor=cursor,
                include_hidden=include_hidden,
                limit=limit,
            )
        )


class _AppsClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncAppsClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def list(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> list[protocol.AppInfo]:
        return self._run(
            self._async_client.list(
                cursor=cursor,
                force_refetch=force_refetch,
                limit=limit,
                thread_id=thread_id,
            )
        )

    def list_page(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> AppListResult:
        return self._run(
            self._async_client.list_page(
                cursor=cursor,
                force_refetch=force_refetch,
                limit=limit,
                thread_id=thread_id,
            )
        )


class _SkillsClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncSkillsClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def list(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> list[SkillsListEntry]:
        return self._run(
            self._async_client.list(
                cwds=cwds,
                force_reload=force_reload,
                per_cwd_extra_user_roots=per_cwd_extra_user_roots,
            )
        )

    def list_page(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> SkillsListResult:
        return self._run(
            self._async_client.list_page(
                cwds=cwds,
                force_reload=force_reload,
                per_cwd_extra_user_roots=per_cwd_extra_user_roots,
            )
        )

    def write_config(self, *, path: str, enabled: bool) -> SkillsConfigWriteResult:
        return self._run(self._async_client.write_config(path=path, enabled=enabled))


class _AccountClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncAccountClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def read(self, *, refresh_token: bool | None = None) -> AccountReadResult:
        return self._run(self._async_client.read(refresh_token=refresh_token))

    def login_api_key(self, *, api_key: str) -> ApiKeyLoginResult:
        return self._run(self._async_client.login_api_key(api_key=api_key))

    def login_chatgpt(self) -> ChatGptLoginResult:
        return self._run(self._async_client.login_chatgpt())

    def login_chatgpt_tokens(
        self,
        *,
        access_token: str,
        chatgpt_account_id: str,
        chatgpt_plan_type: protocol.PlanType | None = None,
    ) -> ChatGptAuthTokensLoginResult:
        return self._run(
            self._async_client.login_chatgpt_tokens(
                access_token=access_token,
                chatgpt_account_id=chatgpt_account_id,
                chatgpt_plan_type=chatgpt_plan_type,
            )
        )

    def cancel_login(self, *, login_id: str) -> AccountCancelLoginResult:
        return self._run(self._async_client.cancel_login(login_id=login_id))

    def logout(self) -> EmptyResult:
        return self._run(self._async_client.logout())

    def read_rate_limits(self) -> AccountRateLimitsResult:
        return self._run(self._async_client.read_rate_limits())


class _ConfigClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncConfigClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def read(
        self,
        *,
        cwd: str | None = None,
        include_layers: bool | None = None,
    ) -> ConfigReadResult:
        return self._run(self._async_client.read(cwd=cwd, include_layers=include_layers))

    def reload_mcp_servers(self) -> EmptyResult:
        return self._run(self._async_client.reload_mcp_servers())

    def write_value(
        self,
        *,
        key_path: str,
        value: Any,
        merge_strategy: protocol.MergeStrategy,
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult:
        return self._run(
            self._async_client.write_value(
                key_path=key_path,
                value=value,
                merge_strategy=merge_strategy,
                expected_version=expected_version,
                file_path=file_path,
            )
        )

    def batch_write(
        self,
        *,
        edits: Sequence[protocol.ConfigEdit],
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult:
        return self._run(
            self._async_client.batch_write(
                edits=edits,
                expected_version=expected_version,
                file_path=file_path,
            )
        )

    def read_requirements(self) -> ConfigRequirementsReadResult:
        return self._run(self._async_client.read_requirements())


class _McpServersClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncMcpServersClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def oauth_login(
        self,
        *,
        name: str,
        scopes: Sequence[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> McpServerOauthLoginResult:
        return self._run(
            self._async_client.oauth_login(
                name=name,
                scopes=scopes,
                timeout_seconds=timeout_seconds,
            )
        )

    def list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> list[McpServerStatus]:
        return self._run(self._async_client.list(cursor=cursor, limit=limit))

    def list_page(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> McpServerStatusListResult:
        return self._run(self._async_client.list_page(cursor=cursor, limit=limit))

    # Backward-compatible aliases; prefer list()/list_page().
    list_status = list
    list_status_page = list_page


class _FeedbackClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncFeedbackClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def upload(
        self,
        *,
        classification: str,
        include_logs: bool,
        extra_log_files: Sequence[str] | None = None,
        reason: str | None = None,
        thread_id: str | None = None,
    ) -> FeedbackUploadResult:
        return self._run(
            self._async_client.upload(
                classification=classification,
                include_logs=include_logs,
                extra_log_files=extra_log_files,
                reason=reason,
                thread_id=thread_id,
            )
        )


class _CommandClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncCommandClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def execute(
        self,
        *,
        command: Sequence[str],
        cwd: str | None = None,
        disable_output_cap: bool | None = None,
        disable_timeout: bool | None = None,
        env: Mapping[str, object | None] | None = None,
        output_bytes_cap: int | None = None,
        process_id: str | None = None,
        sandbox_policy: protocol.SandboxPolicy | None = None,
        size: protocol.CommandExecTerminalSize | None = None,
        stream_stdin: bool | None = None,
        stream_stdout_stderr: bool | None = None,
        timeout_ms: int | None = None,
        tty: bool | None = None,
    ) -> CommandExecResult:
        return self._run(
            self._async_client.execute(
                command=command,
                cwd=cwd,
                disable_output_cap=disable_output_cap,
                disable_timeout=disable_timeout,
                env=env,
                output_bytes_cap=output_bytes_cap,
                process_id=process_id,
                sandbox_policy=sandbox_policy,
                size=size,
                stream_stdin=stream_stdin,
                stream_stdout_stderr=stream_stdout_stderr,
                timeout_ms=timeout_ms,
                tty=tty,
            )
        )

    exec = execute

    def write_stdin(
        self,
        *,
        process_id: str,
        close_stdin: bool | None = None,
        delta_base64: str | None = None,
    ) -> EmptyResult:
        """Write stdin bytes to a running `command/exec` process or close stdin.

        This wraps the app-server `command/exec/write` request. `delta_base64`
        is optional base64-encoded stdin data; `close_stdin` closes the
        process stdin after the optional write.
        """
        return self._run(
            self._async_client.write_stdin(
                process_id=process_id,
                close_stdin=close_stdin,
                delta_base64=delta_base64,
            )
        )

    def resize_terminal(
        self,
        *,
        process_id: str,
        size: protocol.CommandExecTerminalSize,
    ) -> EmptyResult:
        """Resize the terminal attached to a running `command/exec` process.

        This wraps the app-server `command/exec/resize` request and sends the
        new terminal dimensions as `cols` and `rows`.
        """
        return self._run(self._async_client.resize_terminal(process_id=process_id, size=size))

    def terminate_process(self, *, process_id: str) -> EmptyResult:
        """Terminate a running `command/exec` process.

        This wraps the app-server `command/exec/terminate` request for the
        client-supplied process id.
        """
        return self._run(self._async_client.terminate_process(process_id=process_id))


class _ExternalAgentConfigClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncExternalAgentConfigClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def detect(
        self,
        *,
        cwds: Sequence[str] | None = None,
        include_home: bool | None = None,
    ) -> ExternalAgentConfigDetectResult:
        return self._run(self._async_client.detect(cwds=cwds, include_home=include_home))

    def import_items(
        self,
        *,
        migration_items: Sequence[protocol.ExternalAgentConfigMigrationItem],
    ) -> EmptyResult:
        return self._run(self._async_client.import_items(migration_items=migration_items))


class _WindowsSandboxClient(_SyncRunner):
    def __init__(
        self,
        async_client: _AsyncWindowsSandboxClientLike,
        runner: Callable[[Coroutine[Any, Any, Any]], Any],
    ) -> None:
        super().__init__(runner)
        self._async_client = async_client

    def setup_start(
        self,
        *,
        mode: protocol.WindowsSandboxSetupMode,
        cwd: str | None = None,
    ) -> WindowsSandboxSetupStartResult:
        return self._run(self._async_client.setup_start(mode=mode, cwd=cwd))
