from __future__ import annotations

import pytest
from pydantic import BaseModel

import codex.codex as codex_module
import codex.options as options_module
import codex.thread as thread_module
from codex._turn_options import with_model_output_schema
from codex.app_server.options import (
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
        self.start_calls: list[AppServerThreadStartOptions | None] = []
        self.resume_calls: list[tuple[str, AppServerThreadResumeOptions | None]] = []
        self.account = _FakeAccountClient()

    def close(self) -> None:
        self.close_calls += 1

    def start_thread(
        self,
        options: AppServerThreadStartOptions | None = None,
    ) -> _FakeAppServerThread:
        self.start_calls.append(options)
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
    assert "SupportsAborted" in options_module.__all__
    assert "SupportsIsSet" in options_module.__all__


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
    start_thread = thread_module.Thread(lambda: fake_client, start_options=start_options)

    started = start_thread._ensure_thread()

    assert started.id == "thr-start"
    assert start_thread.id == "thr-start"
    assert fake_client.start_calls == [start_options]
    assert fake_client.resume_calls == []

    resume_options = AppServerThreadResumeOptions(personality=protocol.Personality("friendly"))
    resumed_thread = thread_module.Thread(
        lambda: fake_client,
        resume_options=resume_options,
        thread_id="thr-existing",
    )

    resumed = resumed_thread._ensure_thread()

    assert resumed.id == "thr-existing"
    assert resumed_thread.id == "thr-existing"
    assert fake_client.resume_calls == [("thr-existing", resume_options)]


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
