from __future__ import annotations

import importlib.util as importlib_util

import pytest


def test_basic_import_and_api() -> None:
    import codex

    # Version string exposed and public API imports
    assert isinstance(codex.__version__, str) and len(codex.__version__) > 0

    from codex import CodexClient, CodexConfig, run_exec, run_prompt

    # Instantiate config and client to ensure constructors work
    cfg = CodexConfig()
    client = CodexClient(config=cfg)
    assert isinstance(cfg.model_dump(), dict)
    assert isinstance(client, CodexClient)
    assert callable(run_exec)
    assert callable(run_prompt)


def test_run_exec_behavior_without_native() -> None:
    from codex import CodexNativeError, run_exec

    native_available = importlib_util.find_spec("codex_native") is not None

    if not native_available:
        with pytest.raises(CodexNativeError):
            # Should raise when native extension is not available
            run_exec("hello", load_default_config=False)
    else:
        # When native is available, keep the smoke test lightweight.
        pytest.skip("Native available; skipping heavy run in smoke test.")
