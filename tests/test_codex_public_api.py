from __future__ import annotations

import pytest
from pydantic import BaseModel

import codex
import codex.codex as codex_module
import codex.options as options_module
import codex.thread as thread_module
from codex._turn_options import with_model_output_schema
from codex.app_server.options import (
    AppServerInitializeOptions,
    AppServerProcessOptions,
    AppServerThreadResumeOptions,
    AppServerThreadStartOptions,
    AppServerTurnOptions,
)
from codex.errors import CodexError
from codex.protocol import types as protocol


class _FakeAppServerThread:
    def __init__(self, thread_id: str) -> None:
        self.id = thread_id


class _FakeAccountClient:
    def __init__(self) -> None:
        self.login_api_key_calls: list[str] = []

    def login_api_key(self, *, api_key: str) -> object:
        self.login_api_key_calls.append(api_key)
        return object()


class _FakeAppServerClient:
    def __init__(self) -> None:
        self.close_calls = 0
        self.start_calls: list[tuple[AppServerThreadStartOptions | None, object | None]] = []
        self.resume_calls: list[tuple[str, AppServerThreadResumeOptions | None]] = []
        self.account = _FakeAccountClient()

    def close(self) -> None:
        self.close_calls += 1

    def start_thread(
        self,
        options: AppServerThreadStartOptions | None = None,
        *,
        tools: object | None = None,
    ) -> _FakeAppServerThread:
        self.start_calls.append((options, tools))
        return _FakeAppServerThread("thr-start")

    def resume_thread(
        self,
        thread_id: str,
        options: AppServerThreadResumeOptions | None = None,
    ) -> _FakeAppServerThread:
        self.resume_calls.append((thread_id, options))
        return _FakeAppServerThread(thread_id)


class _SummaryModel(BaseModel):
    answer: str


def test_options_module_re_exports_app_server_option_types() -> None:
    assert options_module.CodexOptions.__name__ == "CodexOptions"
    assert options_module.ThreadStartOptions.__name__ == "ThreadStartOptions"
    assert options_module.ThreadResumeOptions.__name__ == "ThreadResumeOptions"
    assert options_module.TurnOptions.__name__ == "TurnOptions"
    assert not issubclass(options_module.CodexOptions, AppServerProcessOptions)
    assert not issubclass(options_module.ThreadStartOptions, AppServerThreadStartOptions)
    assert not issubclass(options_module.ThreadResumeOptions, AppServerThreadResumeOptions)
    assert not issubclass(options_module.TurnOptions, AppServerTurnOptions)
    assert isinstance(
        options_module.CodexOptions().to_app_server_options(), AppServerProcessOptions
    )
    assert isinstance(
        options_module.ThreadStartOptions().to_app_server_options(),
        AppServerThreadStartOptions,
    )
    assert isinstance(
        options_module.ThreadResumeOptions().to_app_server_options(),
        AppServerThreadResumeOptions,
    )
    assert isinstance(options_module.TurnOptions().to_app_server_options(), AppServerTurnOptions)
    assert "CancelSignal" in options_module.__all__
    assert "CodexConfig" in options_module.__all__
    assert "SupportsAborted" in options_module.__all__
    assert "SupportsIsSet" in options_module.__all__


def test_root_package_exports_dynamic_tool() -> None:
    assert codex.dynamic_tool.__name__ == "dynamic_tool"


def test_exported_codex_option_fields_have_descriptions() -> None:
    option_types = [
        options_module.CodexOptions,
        options_module.ThreadStartOptions,
        options_module.ThreadResumeOptions,
        options_module.TurnOptions,
    ]

    for option_type in option_types:
        for field in option_type.model_fields.values():
            assert field.description

    for field in options_module.CodexConfig.model_fields.values():
        assert field.description


def test_codex_and_app_server_options_coerce_config_dicts_to_typed_model() -> None:
    codex_options = options_module.CodexOptions(config={"profile": "dev", "web_search": "cached"})
    thread_options = options_module.ThreadStartOptions(config={"skip_git_repo_check": True})

    assert isinstance(codex_options.config, options_module.CodexConfig)
    assert codex_options.config is not None
    assert codex_options.config.profile == "dev"
    assert codex_options.config.web_search == "cached"
    assert codex_options.config.model_extra == {}

    app_options = codex_options.to_app_server_options()
    assert app_options.config == codex_options.config

    app_thread_options = thread_options.to_app_server_options()
    assert isinstance(app_thread_options.config, options_module.CodexConfig)
    assert app_thread_options.config is not None
    assert app_thread_options.config.model_extra == {"skip_git_repo_check": True}


def test_codex_caches_stdio_client_and_closes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeAppServerClient()
    captured: list[AppServerProcessOptions] = []

    def fake_connect_stdio(
        cls: type[object],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeAppServerClient:
        _ = (cls, initialize_options)
        assert process_options is not None
        captured.append(process_options)
        return fake_client

    monkeypatch.setattr(
        "codex.app_server.AppServerClient.connect_stdio",
        classmethod(fake_connect_stdio),
    )

    options = codex_module.CodexOptions(base_url="https://example.test")
    client = codex_module.Codex(options)

    first = client._ensure_client()
    second = client._ensure_client()

    assert first is fake_client
    assert second is fake_client
    assert captured == [options.to_app_server_options()]

    client.close()
    client.close()

    assert fake_client.close_calls == 1

    with pytest.raises(CodexError, match="closed"):
        client.start_thread()


def test_codex_logs_in_via_app_server_account_client_when_api_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeAppServerClient()

    def fake_connect_stdio(
        cls: type[object],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeAppServerClient:
        _ = (cls, process_options, initialize_options)
        return fake_client

    monkeypatch.setattr(
        "codex.app_server.AppServerClient.connect_stdio",
        classmethod(fake_connect_stdio),
    )

    client = codex_module.Codex(codex_module.CodexOptions(api_key="sk-test"))

    assert client._ensure_client() is fake_client
    assert fake_client.account.login_api_key_calls == ["sk-test"]


def test_codex_resume_thread_rejects_empty_id() -> None:
    client = codex_module.Codex()

    with pytest.raises(ValueError, match="thread_id must be non-empty"):
        client.resume_thread("")


def test_thread_ensure_thread_uses_start_and_resume_options() -> None:
    fake_client = _FakeAppServerClient()

    start_options = AppServerThreadStartOptions(model="gpt-5")
    start_thread = thread_module.Thread(
        lambda **_: fake_client,
        start_options=start_options,
    )

    started = start_thread._ensure_thread()

    assert started.id == "thr-start"
    assert start_thread.id == "thr-start"
    assert fake_client.start_calls == [(start_options, None)]
    assert fake_client.resume_calls == []

    resume_options = AppServerThreadResumeOptions(personality=protocol.Personality("friendly"))
    resumed_thread = thread_module.Thread(
        lambda **_: fake_client,
        resume_options=resume_options,
        thread_id="thr-existing",
    )

    resumed = resumed_thread._ensure_thread()

    assert resumed.id == "thr-existing"
    assert resumed_thread.id == "thr-existing"
    assert fake_client.resume_calls == [("thr-existing", resume_options)]


def test_codex_start_thread_passes_annotation_driven_tools_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeAppServerClient()
    captured: dict[str, object] = {}

    def fake_connect_stdio(
        cls: type[object],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeAppServerClient:
        _ = (cls, process_options)
        captured["initialize_options"] = initialize_options
        return fake_client

    monkeypatch.setattr(
        "codex.app_server.AppServerClient.connect_stdio",
        classmethod(fake_connect_stdio),
    )

    @codex.dynamic_tool
    def lookup_ticket(id: str) -> str:
        """Look up a support ticket by id."""
        return id

    thread = codex_module.Codex().start_thread(tools=[lookup_ticket])

    assert thread.id == "thr-start"
    assert fake_client.start_calls == [(AppServerThreadStartOptions(), [lookup_ticket])]
    assert captured["initialize_options"] == AppServerInitializeOptions(experimental_api=True)


def test_codex_rejects_dynamic_tools_after_non_experimental_client_is_initialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeAppServerClient()

    def fake_connect_stdio(
        cls: type[object],
        process_options: AppServerProcessOptions | None = None,
        initialize_options: object | None = None,
    ) -> _FakeAppServerClient:
        _ = (cls, process_options, initialize_options)
        return fake_client

    monkeypatch.setattr(
        "codex.app_server.AppServerClient.connect_stdio",
        classmethod(fake_connect_stdio),
    )

    client = codex_module.Codex()
    client.start_thread()

    @codex.dynamic_tool
    def lookup_ticket(id: str) -> str:
        """Look up a support ticket by id."""
        return id

    with pytest.raises(CodexError, match="Dynamic tools require experimentalApi"):
        client.start_thread(tools=[lookup_ticket])


def test_thread_signal_helpers_validate_supported_signal_shapes() -> None:
    class _AbortedSignal:
        aborted = True

    class _EventSignal:
        def __init__(self, is_set_value: bool) -> None:
            self._is_set_value = is_set_value

        def is_set(self) -> bool:
            return self._is_set_value

    assert thread_module._is_signal_aborted(_AbortedSignal()) is True
    assert thread_module._is_signal_aborted(_EventSignal(True)) is True
    assert thread_module._is_signal_aborted(_EventSignal(False)) is False

    with pytest.raises(TypeError, match="signal must expose"):
        thread_module._is_signal_aborted(object())  # type: ignore[arg-type]


def test_turn_options_with_model_schema_uses_model_schema_when_missing() -> None:
    generated = with_model_output_schema(None, _SummaryModel, owner="test")

    assert generated.output_schema is _SummaryModel

    updated = with_model_output_schema(AppServerTurnOptions(), _SummaryModel, owner="test")

    assert updated.output_schema is _SummaryModel


def test_turn_options_with_model_schema_rejects_conflicting_output_schema() -> None:
    existing = AppServerTurnOptions(output_schema={"type": "object"})

    with pytest.raises(ValueError, match="test received both model_type"):
        with_model_output_schema(existing, _SummaryModel, owner="test")


def test_turn_options_with_model_schema_allows_equivalent_existing_schema() -> None:
    existing = AppServerTurnOptions(output_schema=_SummaryModel.model_json_schema())

    updated = with_model_output_schema(existing, _SummaryModel, owner="test")

    assert updated.output_schema == _SummaryModel.model_json_schema()
