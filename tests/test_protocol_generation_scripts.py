from __future__ import annotations

import builtins
import importlib.util
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_script_module(name: str, relative_path: str) -> ModuleType:
    path = Path(relative_path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load script module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_protocol_types_exposes_named_stage_commands() -> None:
    module = _load_script_module("generate_protocol_types", "scripts/generate_protocol_types.py")

    schema_command = module.build_schema_export_command(
        codex_bin="/tmp/codex",
        schema_dir=Path("/tmp/schema-dir"),
        experimental=True,
    )
    codegen_command = module.build_datamodel_codegen_command(
        schema_path=Path("/tmp/schema-dir/codex_app_server_protocol.schemas.json"),
        output_path=Path("/tmp/types.py"),
    )

    assert schema_command == [
        "/tmp/codex",
        "app-server",
        "generate-json-schema",
        "--out",
        "/tmp/schema-dir",
        "--experimental",
    ]
    assert codegen_command == [
        "uvx",
        "--from",
        module.DATAMODEL_CODE_GENERATOR_PACKAGE,
        "datamodel-codegen",
        "--input",
        "/tmp/schema-dir/codex_app_server_protocol.schemas.json",
        "--input-file-type",
        "jsonschema",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.12",
        "--use-annotated",
        "--use-title-as-name",
        "--enum-field-as-literal",
        "all",
        "--use-double-quotes",
        "--output",
        "/tmp/types.py",
    ]


def test_generate_protocol_types_run_stage_sets_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module("generate_protocol_types", "scripts/generate_protocol_types.py")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], *, check: bool, timeout: int) -> None:
        captured["command"] = command
        captured["check"] = check
        captured["timeout"] = timeout

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.run_stage("example", ["echo", "ok"])

    assert captured == {
        "command": ["echo", "ok"],
        "check": True,
        "timeout": module.SUBPROCESS_TIMEOUT_SECONDS,
    }


def test_generate_protocol_types_postprocesses_requested_output_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module("generate_protocol_types", "scripts/generate_protocol_types.py")
    captured: dict[str, object] = {}

    def fake_run_stage(name: str, command: list[str]) -> None:
        captured["name"] = name
        captured["command"] = command

    monkeypatch.setattr(module, "run_stage", fake_run_stage)

    module.postprocess_protocol_models(Path("/tmp/current-types.py"))

    assert captured == {
        "name": "postprocess generated protocol types",
        "command": [
            sys.executable,
            "scripts/postprocess_protocol_types.py",
            "/tmp/current-types.py",
        ],
    }


@pytest.mark.parametrize("failure", ["extra", "postprocess", None])
@pytest.mark.parametrize("destination", ["existing", "absent", "symlink"])
def test_generate_protocol_types_publishes_only_complete_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str | None,
    destination: str,
) -> None:
    module = _load_script_module("generate_protocol_types", "scripts/generate_protocol_types.py")
    postprocessor = _load_script_module(
        "postprocess_protocol_types", "scripts/postprocess_protocol_types.py"
    )
    output = tmp_path / "types.py"
    original = b"# original contract\n"
    target = tmp_path / "linked.py"
    if destination == "symlink":
        if sys.platform == "win32":
            pytest.skip("Creating symlinks requires privileges on Windows")
        target.write_bytes(original)
        output.symlink_to(target)
    elif destination == "existing":
        output.write_bytes(original)
        output.chmod(0o644)
    original_paths = set(tmp_path.iterdir())

    def fake_run_stage(name: str, command: list[str]) -> None:
        if command[0] == "fake-codex":
            schema_dir = Path(command[command.index("--out") + 1])
            (schema_dir / "codex_app_server_protocol.schemas.json").write_text("{}")
            (schema_dir / "v2").mkdir()
            (schema_dir / "v2" / "ExtraResponse.json").write_text("{}")
        elif command[0] == "uvx":
            generated_path = Path(command[command.index("--output") + 1])
            extra = Path(command[command.index("--input") + 1]).stem == "ExtraResponse"
            generated_path.write_text("class Extra: pass\n" if extra else "class Primary: pass\n")
            if extra and failure == "extra":
                raise subprocess.CalledProcessError(1, command)
        else:
            assert command[1] == "scripts/postprocess_protocol_types.py"
            postprocessor.postprocess_file(Path(command[2]))
            if failure == "postprocess":
                raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(module, "run_stage", fake_run_stage)
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_protocol_types.py", "--codex-bin", "fake-codex", "--output", str(output)],
    )

    if failure is not None:
        with pytest.raises(subprocess.CalledProcessError):
            module.main()
        if destination == "absent":
            assert not output.exists()
        else:
            assert output.read_bytes() == original
            assert output.is_symlink() == (destination == "symlink")
    else:
        assert module.main() == 0
        text = output.read_text()
        assert "class Primary: pass" in text
        assert "class Extra: pass" in text
        assert "from __future__ import annotations" in text
        assert not output.is_symlink()
        if sys.platform != "win32":
            assert stat.S_IMODE(output.stat().st_mode) == 0o600

    if destination == "symlink":
        assert target.read_bytes() == original
    assert set(tmp_path.iterdir()) == original_paths | ({output} if failure is None else set())


def test_generate_protocol_types_inserts_extra_response_models_before_rebuilds(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "generate_protocol_types_extra", "scripts/generate_protocol_types.py"
    )
    target_path = tmp_path / "types.py"
    generated_path = tmp_path / "ListMcpServerStatusResponse.py"
    target_path.write_text(
        "# generated by datamodel-codegen:\n"
        "from pydantic import BaseModel\n\n"
        "class Existing(BaseModel):\n"
        "    pass\n\n"
        "ClientRequest.model_rebuild()\n",
        encoding="utf-8",
    )
    generated_path.write_text(
        "# generated by datamodel-codegen:\n"
        "from pydantic import BaseModel\n\n"
        "class Existing(BaseModel):\n"
        "    duplicate: bool\n\n"
        "class ListMcpServerStatusResponse(BaseModel):\n"
        "    data: list[str]\n\n"
        "ListMcpServerStatusResponse.model_rebuild()\n",
        encoding="utf-8",
    )

    appended = module.append_generated_model_definitions(
        target_path=target_path,
        generated_path=generated_path,
    )

    assert appended == 1
    assert target_path.read_text(encoding="utf-8") == (
        "# generated by datamodel-codegen:\n"
        "from pydantic import BaseModel\n\n"
        "class Existing(BaseModel):\n"
        "    pass\n\n"
        "class ListMcpServerStatusResponse(BaseModel):\n"
        "    data: list[str]\n\n"
        "ClientRequest.model_rebuild()\n"
    )


def test_generate_protocol_types_discovers_all_v2_response_schema_files(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "generate_protocol_types_response_discovery", "scripts/generate_protocol_types.py"
    )
    v2_dir = tmp_path / "v2"
    v2_dir.mkdir()
    (v2_dir / "ModelListResponse.json").write_text("{}", encoding="utf-8")
    (v2_dir / "ThreadStartResponse.json").write_text("{}", encoding="utf-8")
    (v2_dir / "ThreadStartParams.json").write_text("{}", encoding="utf-8")

    assert [path.name for path in module.extra_protocol_schema_paths(tmp_path)] == [
        "ModelListResponse.json",
        "ThreadStartResponse.json",
    ]


def test_postprocess_protocol_types_main_uses_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "postprocess_protocol_types",
        "scripts/postprocess_protocol_types.py",
    )
    default_path = tmp_path / "default-types.py"
    explicit_path = tmp_path / "explicit-types.py"
    default_path.write_text("# generated by datamodel-codegen:\nclass DefaultOnly: ...\n")
    explicit_path.write_text(
        "# generated by datamodel-codegen:\nclass EventMsg(RootModel[Foo | Bar]):\n    pass\n"
    )
    monkeypatch.setattr(module, "DEFAULT_PROTOCOL_TYPES_PATH", default_path)
    monkeypatch.setattr(sys, "argv", ["postprocess_protocol_types.py", str(explicit_path)])

    module.main()

    assert "class DefaultOnly" in default_path.read_text()
    assert "class EventMsg(RootModel):" in explicit_path.read_text()


def test_postprocess_protocol_types_does_not_import_codex_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def reject_codex_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "codex" or name.startswith("codex."):
            raise AssertionError(f"unexpected package import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_codex_import)

    module = _load_script_module(
        "postprocess_protocol_types_no_package_import",
        "scripts/postprocess_protocol_types.py",
    )

    processed, _ = module.postprocess_types(
        "# generated by datamodel-codegen:\nclass EventMsg(RootModel[Foo | Bar]):\n    pass\n"
    )

    assert "class EventMsg(RootModel):" in processed


def test_postprocess_types_applies_explicit_pipeline_passes() -> None:
    module = _load_script_module(
        "postprocess_protocol_types",
        "scripts/postprocess_protocol_types.py",
    )

    raw = """# generated by datamodel-codegen:\nfrom typing import Annotated, Any, Literal\n\nfrom pydantic import BaseModel, Field, RootModel\n\nclass EventMsg(RootModel[Foo | Bar]):\n    pass\nclass Record3Cstring2Cnever3E(BaseModel):\n    pass\nclass Example(RootModel[JsonValue]):\n    root: JsonValue\nitems: list[JsonValue]\nmapping: dict[str, JsonValue]\nserviceTier: str | None = None\nservice_tier: str | None = None\nserviceTier: Annotated[\n        str | None,\n        Field(description=\"Override the service tier for this turn and subsequent turns.\"),\n    ] = None\nEventMsg.model_rebuild()\nEventMsg.model_rebuild()\n"""
    raw += """scope: Annotated[PermissionGrantScope | None, Field(validate_default=True)] = "turn"\naccess: Annotated[ReadOnlyAccess | None, Field(validate_default=True)] = {"type": "fullAccess"}\nnetworkAccess: Annotated[NetworkAccess | None, Field(validate_default=True)] = (\n    "restricted"\n)\nsource: Annotated[CommandExecutionSource | None, Field(validate_default=True)] = "agent"\nsource: Annotated[HookSource | None, Field(validate_default=True)] = "unknown"\nrole: Annotated[ConversationTextRole | None, Field(validate_default=True)] = "user"\nmultiAgentMode: Annotated[MultiAgentMode | None, Field(validate_default=True)] = "explicitRequestOnly"\nhistoryMode: Annotated[ThreadHistoryMode | None, Field(validate_default=True)] = "legacy"\ncredentialSource: Annotated[AmazonBedrockCredentialSource | None, Field(validate_default=True)] = "awsManaged"\nitemsView: Annotated[\n    TurnItemsView | None,\n    Field(description=\"Loaded item view.\", validate_default=True),\n] = \"full\"\navailability: Annotated[\n    PluginAvailability | None,\n    Field(description=\"Plugin availability.\", validate_default=True),\n] = \"AVAILABLE\"\ninputModalities: Annotated[list[InputModality] | None, Field(validate_default=True)] = ["text", "image"]\n"""
    raw += """kind: Annotated[\n    CommandExecutionApprovalKind | None,\n    Field(description=\"Approval kind.\", validate_default=True),\n] = \"command\"\n"""

    processed, removed = module.postprocess_types(raw)

    assert "# ruff: noqa: F821" in processed
    assert "# mypy: ignore-errors" not in processed
    assert "class EventMsg(RootModel):" in processed
    assert "class EmptyObject(BaseModel):" in processed
    assert "RootModel['JsonValue']" in processed
    assert "list['JsonValue']" in processed
    assert "dict[str, 'JsonValue']" in processed
    assert "from typing import Annotated, Any, Literal, NewType" in processed
    assert 'ServiceTier = NewType("ServiceTier", str)' in processed
    assert "serviceTier: ServiceTier | None = None" in processed
    assert "service_tier: ServiceTier | None = None" in processed
    assert "serviceTier: Annotated[\n        ServiceTier | None," in processed
    assert (
        "scope: Annotated[PermissionGrantScope | None, Field(validate_default=True)] = "
        'PermissionGrantScope("turn")'
    ) in processed
    assert (
        "access: Annotated[ReadOnlyAccess | None, Field(validate_default=True)] = "
        'ReadOnlyAccess.model_validate({"type": "fullAccess"})'
    ) in processed
    assert (
        "networkAccess: Annotated[NetworkAccess | None, Field(validate_default=True)] = "
        'NetworkAccess("restricted")'
    ) in processed
    assert (
        "source: Annotated[CommandExecutionSource | None, Field(validate_default=True)] = "
        'CommandExecutionSource("agent")'
    ) in processed
    assert (
        "role: Annotated[ConversationTextRole | None, Field(validate_default=True)] = "
        'ConversationTextRole("user")'
    ) in processed
    assert (
        'source: Annotated[HookSource | None, Field(validate_default=True)] = HookSource("unknown")'
    ) in processed
    assert '] = MultiAgentMode("explicitRequestOnly")' in processed
    assert '] = ThreadHistoryMode("legacy")' in processed
    assert '] = AmazonBedrockCredentialSource("awsManaged")' in processed
    assert '] = TurnItemsView("full")' in processed
    assert '] = PluginAvailability("AVAILABLE")' in processed
    assert '] = CommandExecutionApprovalKind("command")' in processed
    assert (
        "inputModalities: Annotated[list[InputModality] | None, Field(validate_default=True)] = "
        '[InputModality("text"), InputModality("image")]'
    ) in processed
    assert processed.count("EventMsg.model_rebuild()") == 1
    assert removed == 2


def test_postprocess_types_exposes_union_rootmodel_value_aliases() -> None:
    module = _load_script_module(
        "postprocess_protocol_types_aliases",
        "scripts/postprocess_protocol_types.py",
    )

    raw = """# generated by datamodel-codegen:
from pydantic import BaseModel, Field, RootModel
from typing import Annotated

class FooNotification(BaseModel):
    value: str

class BarNotification(BaseModel):
    value: int

class ServerNotification(RootModel[FooNotification | BarNotification]):
    root: Annotated[
        FooNotification
        | BarNotification,
        Field(title="ServerNotification"),
    ]
"""

    processed, _ = module.postprocess_types(raw)

    assert (
        "type ServerNotificationValue = (\n"
        "    FooNotification\n"
        "    | BarNotification\n"
        ")\n\n"
        "class ServerNotification(RootModel):"
    ) in processed
    assert (
        "class ServerNotification(RootModel):\n"
        "    root: Annotated[\n"
        "        ServerNotificationValue,\n"
        '        Field(title="ServerNotification"),\n'
        "    ]"
    ) in processed
