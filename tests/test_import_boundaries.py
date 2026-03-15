from __future__ import annotations

import importlib


def test_root_package_exposes_only_high_level_contract() -> None:
    codex = importlib.import_module("codex")

    assert codex.Codex.__name__ == "Codex"
    assert codex.CodexTurnStream.__name__ == "CodexTurnStream"
    assert codex.Thread.__name__ == "Thread"
    assert codex.Input.__name__ == "Input"
    assert codex.CodexConfig.__name__ == "CodexConfig"
    assert callable(codex.dynamic_tool)
    assert codex.ThreadStartOptions.__name__ == "ThreadStartOptions"
    assert codex.ThreadResumeOptions.__name__ == "ThreadResumeOptions"
    assert not hasattr(codex, "ExecTurnStream")
    assert not hasattr(codex, "UserInput")
    assert not hasattr(codex, "AppServerClient")
    assert not hasattr(codex, "AsyncAppServerClient")
    assert not hasattr(codex, "ThreadOptions")
    assert not hasattr(codex, "ApprovalMode")
    assert not hasattr(codex, "SandboxMode")
    assert not hasattr(codex, "ModelReasoningEffort")
    assert not hasattr(codex, "WebSearchMode")


def test_app_server_package_exposes_supported_surface_only() -> None:
    app_server = importlib.import_module("codex.app_server")

    assert app_server.AppServerClient.__name__ == "AppServerClient"
    assert app_server.AsyncAppServerClient.__name__ == "AsyncAppServerClient"
    assert app_server.AppServerClientInfo.__name__ == "AppServerClientInfo"
    assert app_server.CodexConfig.__name__ == "CodexConfig"
    assert callable(app_server.dynamic_tool)
    assert not hasattr(app_server, "GenericNotification")
    assert not hasattr(app_server, "GenericServerRequest")
    assert not hasattr(app_server, "AsyncStdioTransport")
    assert not hasattr(app_server, "AsyncWebSocketTransport")


def test_app_server_helpers_share_internal_json_alias() -> None:
    payloads = importlib.import_module("codex.app_server._payloads")
    protocol_helpers = importlib.import_module("codex.app_server._protocol_helpers")
    internal_types = importlib.import_module("codex.app_server._types")

    assert payloads.JsonObject is internal_types.JsonObject
    assert protocol_helpers.JsonObject is internal_types.JsonObject


def test_exported_app_server_option_fields_have_descriptions() -> None:
    options_module = importlib.import_module("codex.app_server.options")
    app_server = importlib.import_module("codex.app_server")
    config_module = importlib.import_module("codex._config_types")

    option_types = [
        getattr(options_module, name)
        for name in app_server.__all__
        if name == "AppServerClientInfo" or name.endswith("Options")
    ]

    for option_type in option_types:
        for field in option_type.model_fields.values():
            assert field.description

    for field in config_module.CodexConfig.model_fields.values():
        assert field.description
