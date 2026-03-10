from __future__ import annotations

from dataclasses import dataclass, field

from codex.options import CodexConfigObject


@dataclass(slots=True, frozen=True)
class AppServerClientInfo:
    name: str
    version: str
    title: str | None = None

    def to_payload(self) -> dict[str, str]:
        payload = {
            "name": self.name,
            "version": self.version,
        }
        if self.title is not None:
            payload["title"] = self.title
        return payload


@dataclass(slots=True, frozen=True)
class AppServerInitializeOptions:
    client_info: AppServerClientInfo = field(
        default_factory=lambda: AppServerClientInfo(
            name="codex_python",
            title="codex-python",
            version="dev",
        )
    )
    experimental_api: bool = False
    opt_out_notification_methods: tuple[str, ...] = ()

    def to_params(self) -> dict[str, object]:
        params: dict[str, object] = {
            "clientInfo": self.client_info.to_payload(),
        }
        capabilities: dict[str, object] = {}
        if self.experimental_api:
            capabilities["experimentalApi"] = True
        if self.opt_out_notification_methods:
            capabilities["optOutNotificationMethods"] = list(self.opt_out_notification_methods)
        if capabilities:
            params["capabilities"] = capabilities
        return params


@dataclass(slots=True, frozen=True)
class AppServerProcessOptions:
    codex_path_override: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    config: CodexConfigObject | None = None
    env: dict[str, str] | None = None
    analytics_default_enabled: bool = False
