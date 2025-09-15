# codex-python

Native Python bindings for Codex (in‑process execution). Ships as a single package (`codex-python`) with platform wheels that include the native extension.

- Python: 3.12–3.13 (CI also attempts 3.14)
- Import name: `codex`
- PyPI: https://pypi.org/project/codex-python/

## Install

```
pip install codex-python
```

If there’s no prebuilt wheel for your platform/Python, pip will build from source. You’ll need a Rust toolchain and maturin; see “Developing” below.

## Quickstart

Run a prompt and collect structured events (typed):

```
from codex.api import run_exec, CodexClient
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode

cfg = CodexConfig(
    model="gpt-5",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
)

# One-shot
events = run_exec("Explain this repo", config=cfg)

# Conversation (streaming)
client = CodexClient(config=cfg)
for ev in client.start_conversation("Add a smoke test"):
    print(ev.id, ev.msg)
```

Notes
- `Event.msg` is typed as a union `EventMsg` (also available at `codex.EventMsg`).
- For raw dict streaming from the native layer, use `codex.native.start_exec_stream`.

## Configuration (Pydantic)

Use `CodexConfig` to pass overrides mirrored from Rust `ConfigOverrides`.

```
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode

cfg = CodexConfig(
    model="gpt-5",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    cwd="/path/to/project",
    include_apply_patch_tool=True,
)
```

- `CodexConfig.to_dict()` emits only fields you set, with enums serialized to kebab‑case strings expected by the core.
- For tests and introspection, `codex.native.preview_config(config_overrides=..., load_default_config=...)` returns a compact snapshot of the effective configuration.

## Troubleshooting

- “codex_native extension not installed”
  - Install with `pip install codex-python` (wheel) or build locally (see below).
- maturin develop fails without a virtualenv
  - Use `python -m venv .venv && source .venv/bin/activate` (or conda), or run `make dev-native` which falls back to build+pip install when no venv is present.

## Developing

Prerequisites
- Python 3.12/3.13
- Rust toolchain (cargo)
- maturin (for native builds)
- uv (optional, for fast Python builds and dev tooling)

Common tasks
- Lint: `make lint` (ruff + mypy)
- Test: `make test` (pytest)
- Format: `make fmt`
- Build native locally: `make dev-native`
- Generate protocol types from upstream: `make gen-protocol`

Protocol types
- `make gen-protocol` generates TS types and a JSON Schema, then writes Pydantic v2 models to `codex/protocol/types.py`. The process runs entirely from the native helper in this repo; no manual scripts needed.
- Generated models use `model_config = ConfigDict(extra='allow')` and place it at the end of each class.

Releasing
- Bump `codex/__init__.py` and `crates/codex_native/Cargo.toml` versions.
- Update `CHANGELOG.md`.
- Tag and push: `git tag -a vX.Y.Z -m "codex-python X.Y.Z" && git push origin vX.Y.Z`.
- GitHub Actions (publish.yml) builds native wheels across platforms and an sdist, then publishes them via Trusted Publishing (OIDC).

Project layout
```
.
├── codex/                 # Python package
├── crates/codex_native/   # PyO3 native extension
├── scripts/               # generators and helpers
├── .github/workflows/     # CI, publish, native wheels
└── Makefile               # common tasks
```

Links
- Codex repo: https://github.com/openai/codex
- uv: https://docs.astral.sh/uv/
- maturin: https://www.maturin.rs/

## GitHub Workflow: Autonomous Review

This repo includes a workflow that runs autonomous code review on pull requests and can
apply edits on demand via a slash command.

- Automatic review runs on PR open, synchronize, reopen, and when marked ready for review.
- To request autonomous edits on a PR, comment `/codex` in either a PR thread or a
  review comment. The workflow listens for `/codex` and triggers the "act" job.

See `.github/workflows/codex-autoreview.yml` for configuration.
