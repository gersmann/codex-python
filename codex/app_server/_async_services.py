from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

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

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class _TypedRpcClient(Protocol):
    async def request_typed(
        self,
        method: str,
        params: BaseModel | Mapping[str, object] | None,
        result_model: type[_ModelT],
    ) -> _ModelT: ...


class _AsyncServiceClient:
    def __init__(self, rpc: _TypedRpcClient) -> None:
        self._rpc = rpc


class AsyncModelsClient(_AsyncServiceClient):
    async def list(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> list[ModelInfo]:
        return (
            await self.list_page(cursor=cursor, include_hidden=include_hidden, limit=limit)
        ).data

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        include_hidden: bool | None = None,
        limit: int | None = None,
    ) -> ModelListResult:
        params = protocol.ModelListParams(cursor=cursor, includeHidden=include_hidden, limit=limit)
        return await self._rpc.request_typed("model/list", params, ModelListResult)


class AsyncAppsClient(_AsyncServiceClient):
    async def list(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> list[protocol.AppInfo]:
        return (
            await self.list_page(
                cursor=cursor,
                force_refetch=force_refetch,
                limit=limit,
                thread_id=thread_id,
            )
        ).data

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        force_refetch: bool | None = None,
        limit: int | None = None,
        thread_id: str | None = None,
    ) -> AppListResult:
        params = protocol.AppsListParams(
            cursor=cursor,
            forceRefetch=force_refetch,
            limit=limit,
            threadId=thread_id,
        )
        return await self._rpc.request_typed("app/list", params, AppListResult)


class AsyncSkillsClient(_AsyncServiceClient):
    async def list(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> list[SkillsListEntry]:
        return (
            await self.list_page(
                cwds=cwds,
                force_reload=force_reload,
                per_cwd_extra_user_roots=per_cwd_extra_user_roots,
            )
        ).data

    async def list_page(
        self,
        *,
        cwds: Sequence[str] | None = None,
        force_reload: bool | None = None,
        per_cwd_extra_user_roots: Sequence[protocol.SkillsListExtraRootsForCwd] | None = None,
    ) -> SkillsListResult:
        params = protocol.SkillsListParams(
            cwds=list(cwds) if cwds is not None else None,
            forceReload=force_reload,
            perCwdExtraUserRoots=(
                list(per_cwd_extra_user_roots) if per_cwd_extra_user_roots is not None else None
            ),
        )
        return await self._rpc.request_typed("skills/list", params, SkillsListResult)

    async def write_config(self, *, path: str, enabled: bool) -> SkillsConfigWriteResult:
        params = protocol.SkillsConfigWriteParams(
            path=protocol.AbsolutePathBuf(path),
            enabled=enabled,
        )
        return await self._rpc.request_typed("skills/config/write", params, SkillsConfigWriteResult)


class AsyncAccountClient(_AsyncServiceClient):
    async def read(self, *, refresh_token: bool | None = None) -> AccountReadResult:
        params = protocol.GetAccountParams(refreshToken=refresh_token)
        return await self._rpc.request_typed("account/read", params, AccountReadResult)

    async def login_api_key(self, *, api_key: str) -> ApiKeyLoginResult:
        params = protocol.LoginAccountParams.model_validate({"type": "apiKey", "apiKey": api_key})
        return await self._rpc.request_typed("account/login/start", params, ApiKeyLoginResult)

    async def login_chatgpt(self) -> ChatGptLoginResult:
        params = protocol.LoginAccountParams.model_validate({"type": "chatgpt"})
        return await self._rpc.request_typed("account/login/start", params, ChatGptLoginResult)

    async def login_chatgpt_tokens(
        self,
        *,
        access_token: str,
        chatgpt_account_id: str,
        chatgpt_plan_type: protocol.PlanType | None = None,
    ) -> ChatGptAuthTokensLoginResult:
        params = protocol.LoginAccountParams.model_validate(
            {
                "type": "chatgptAuthTokens",
                "accessToken": access_token,
                "chatgptAccountId": chatgpt_account_id,
                "chatgptPlanType": (
                    chatgpt_plan_type.root if chatgpt_plan_type is not None else None
                ),
            }
        )
        return await self._rpc.request_typed(
            "account/login/start",
            params,
            ChatGptAuthTokensLoginResult,
        )

    async def cancel_login(self, *, login_id: str) -> AccountCancelLoginResult:
        params = protocol.CancelLoginAccountParams(loginId=login_id)
        return await self._rpc.request_typed(
            "account/login/cancel",
            params,
            AccountCancelLoginResult,
        )

    async def logout(self) -> EmptyResult:
        return await self._rpc.request_typed("account/logout", None, EmptyResult)

    async def read_rate_limits(self) -> AccountRateLimitsResult:
        return await self._rpc.request_typed(
            "account/rateLimits/read",
            None,
            AccountRateLimitsResult,
        )


class AsyncConfigClient(_AsyncServiceClient):
    async def read(
        self,
        *,
        cwd: str | None = None,
        include_layers: bool | None = None,
    ) -> ConfigReadResult:
        params = protocol.ConfigReadParams(cwd=cwd, includeLayers=include_layers)
        return await self._rpc.request_typed("config/read", params, ConfigReadResult)

    async def reload_mcp_servers(self) -> EmptyResult:
        return await self._rpc.request_typed("config/mcpServer/reload", None, EmptyResult)

    async def write_value(
        self,
        *,
        key_path: str,
        value: Any,
        merge_strategy: protocol.MergeStrategy,
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult:
        params = protocol.ConfigValueWriteParams(
            expectedVersion=expected_version,
            filePath=file_path,
            keyPath=key_path,
            mergeStrategy=merge_strategy,
            value=value,
        )
        return await self._rpc.request_typed("config/value/write", params, ConfigWriteResult)

    async def batch_write(
        self,
        *,
        edits: Sequence[protocol.ConfigEdit],
        expected_version: str | None = None,
        file_path: str | None = None,
    ) -> ConfigWriteResult:
        params = protocol.ConfigBatchWriteParams(
            edits=list(edits),
            expectedVersion=expected_version,
            filePath=file_path,
        )
        return await self._rpc.request_typed("config/batchWrite", params, ConfigWriteResult)

    async def read_requirements(self) -> ConfigRequirementsReadResult:
        return await self._rpc.request_typed(
            "configRequirements/read",
            None,
            ConfigRequirementsReadResult,
        )


class AsyncMcpServersClient(_AsyncServiceClient):
    async def oauth_login(
        self,
        *,
        name: str,
        scopes: Sequence[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> McpServerOauthLoginResult:
        params = protocol.McpServerOauthLoginParams(
            name=name,
            scopes=list(scopes) if scopes is not None else None,
            timeoutSecs=timeout_seconds,
        )
        return await self._rpc.request_typed(
            "mcpServer/oauth/login",
            params,
            McpServerOauthLoginResult,
        )

    async def list(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> list[McpServerStatus]:
        return (await self.list_page(cursor=cursor, limit=limit)).data

    async def list_page(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> McpServerStatusListResult:
        params = protocol.ListMcpServerStatusParams(cursor=cursor, limit=limit)
        return await self._rpc.request_typed(
            "mcpServerStatus/list",
            params,
            McpServerStatusListResult,
        )

    # Backward-compatible aliases; prefer list()/list_page().
    list_status = list
    list_status_page = list_page


class AsyncFeedbackClient(_AsyncServiceClient):
    async def upload(
        self,
        *,
        classification: str,
        include_logs: bool,
        extra_log_files: Sequence[str] | None = None,
        reason: str | None = None,
        thread_id: str | None = None,
    ) -> FeedbackUploadResult:
        params = protocol.FeedbackUploadParams(
            classification=classification,
            extraLogFiles=list(extra_log_files) if extra_log_files is not None else None,
            includeLogs=include_logs,
            reason=reason,
            threadId=thread_id,
        )
        return await self._rpc.request_typed("feedback/upload", params, FeedbackUploadResult)


class AsyncCommandClient(_AsyncServiceClient):
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
    ) -> CommandExecResult:
        params = protocol.CommandExecParams(
            command=list(command),
            cwd=cwd,
            disableOutputCap=disable_output_cap,
            disableTimeout=disable_timeout,
            env=dict(env) if env is not None else None,
            outputBytesCap=output_bytes_cap,
            processId=process_id,
            sandboxPolicy=sandbox_policy,
            size=size,
            streamStdin=stream_stdin,
            streamStdoutStderr=stream_stdout_stderr,
            timeoutMs=timeout_ms,
            tty=tty,
        )
        return await self._rpc.request_typed("command/exec", params, CommandExecResult)

    exec = execute

    async def write_stdin(
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
        params = protocol.CommandExecWriteParams(
            closeStdin=close_stdin,
            deltaBase64=delta_base64,
            processId=process_id,
        )
        return await self._rpc.request_typed("command/exec/write", params, EmptyResult)

    async def resize(
        self,
        *,
        process_id: str,
        size: protocol.CommandExecTerminalSize,
    ) -> EmptyResult:
        params = protocol.CommandExecResizeParams(processId=process_id, size=size)
        return await self._rpc.request_typed("command/exec/resize", params, EmptyResult)

    async def terminate(self, *, process_id: str) -> EmptyResult:
        params = protocol.CommandExecTerminateParams(processId=process_id)
        return await self._rpc.request_typed("command/exec/terminate", params, EmptyResult)


class AsyncExternalAgentConfigClient(_AsyncServiceClient):
    async def detect(
        self,
        *,
        cwds: Sequence[str] | None = None,
        include_home: bool | None = None,
    ) -> ExternalAgentConfigDetectResult:
        params = protocol.ExternalAgentConfigDetectParams(
            cwds=list(cwds) if cwds is not None else None,
            includeHome=include_home,
        )
        return await self._rpc.request_typed(
            "externalAgentConfig/detect",
            params,
            ExternalAgentConfigDetectResult,
        )

    async def import_items(
        self,
        *,
        migration_items: Sequence[protocol.ExternalAgentConfigMigrationItem],
    ) -> EmptyResult:
        params = protocol.ExternalAgentConfigImportParams(migrationItems=list(migration_items))
        return await self._rpc.request_typed("externalAgentConfig/import", params, EmptyResult)


class AsyncWindowsSandboxClient(_AsyncServiceClient):
    async def setup_start(
        self,
        *,
        mode: protocol.WindowsSandboxSetupMode,
        cwd: str | None = None,
    ) -> WindowsSandboxSetupStartResult:
        params = protocol.WindowsSandboxSetupStartParams(
            cwd=protocol.AbsolutePathBuf(cwd) if cwd is not None else None,
            mode=mode,
        )
        return await self._rpc.request_typed(
            "windowsSandbox/setupStart",
            params,
            WindowsSandboxSetupStartResult,
        )
