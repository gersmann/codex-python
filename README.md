# codex-python

Python interface to Codex, packaged as a single distribution (`codex-python`). Platform wheels include a native extension for in‑process execution. The library consolidates on native bindings (no subprocess wrapper).

## Quickstart

- Requires Python 3.12+.
- Package import name: `codex`.
- Distribution name (PyPI): `codex-python`.

### Repo

- Git: `git@github.com:gersmann/codex-python.git`
- URL: https://github.com/gersmann/codex-python

## Usage

Native, non-interactive execution with Pydantic config:

```
from codex.api import run_exec, CodexClient
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode

cfg = CodexConfig(
    model="gpt-5",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
)

events = run_exec("explain this repo", config=cfg)

client = CodexClient(config=cfg)
for ev in client.start_conversation("add a smoke test"):
    print(ev)
```

To stream raw dict events directly from the native layer:

```
from codex.native import start_exec_stream

for e in start_exec_stream("explain this repo", config_overrides=cfg.to_dict()):
    # each `e` is a dict representing an event envelope
    print(e)
```

The event payload is typed: `Event.msg` is a union `EventMsg` from `codex.protocol.types`,
and is also exported at `codex.EventMsg` for convenience.

### Install uv

- macOS (Homebrew): `brew install uv`
- Or via install script:
  - Unix/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex`

See: https://docs.astral.sh/uv/

### Create a virtual env (optional)

```
uv python install 3.13
uv venv --python 3.13
. .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

### Build

```
uv build
```

Artifacts appear in `dist/` (`.whl` and `.tar.gz`).

### Publish to PyPI

- Manual:

```
export PYPI_API_TOKEN="pypi-XXXX"  # create at https://pypi.org/manage/account/token/
uv publish --token "$PYPI_API_TOKEN"
```

- GitHub Actions (Trusted Publishing): enable PyPI Trusted Publishing for
  `gersmann/codex-python` and push a tag like `v0.1.0`. No token is needed.
  The workflow at `.github/workflows/publish.yml` requests an OIDC token and
  runs `uv publish --trusted-publishing=always` on `v*` tags.

### Dev tooling

- Lint: `make lint` (ruff + mypy)
- Tests: `make test` (pytest)
- Format: `make fmt` (ruff formatter)
 - Pre-commit: `uvx pre-commit install && uvx pre-commit run --all-files`

### Protocol bindings (from codex-rs)

- Prereq: Rust toolchain (`cargo`) installed.
- Generate Python types from the upstream protocol with:

```
make gen-protocol
```

This will:
- emit TypeScript types under `.generated/ts/`
- convert them to Python Pydantic models + Literal unions at `codex/protocol/types.py`

### Native bindings (PyO3)

- Install path

`pip install codex-python` installs a platform wheel that includes the native extension on supported platforms (Python 3.12/3.13; CI also attempts 3.14).

- Build locally (requires Rust + maturin):

```
make dev-native
```

- Notes:
  - The native path embeds Codex directly; no subprocess.
  - A helper `codex.native.preview_config(...)` returns a compact snapshot of the effective configuration (selected fields) for tests and introspection.

### Configuration (Pydantic)

Use the `CodexConfig` Pydantic model to pass overrides which mirror the Rust `ConfigOverrides`:

```
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode
from codex.api import run_exec, CodexClient

cfg = CodexConfig(
    model="gpt-5",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    cwd="/path/to/project",
    include_apply_patch_tool=True,
)

events = run_exec("Explain this project", config=cfg)

client = CodexClient(config=cfg)
for ev in client.start_conversation("Add a test for feature X"):
    print(ev)
```

`CodexConfig.to_dict()` emits only set (non‑None) fields and serializes enums to their kebab‑case strings to match the native Rust types.

## Project Layout

```
.
├── codex/              # package root (import name: codex)
│   └── __init__.py     # version lives here
├── pyproject.toml      # PEP 621 metadata, hatchling build backend
├── README.md
└── .gitignore
```

## Versioning

Version is managed via `codex/__init__.py` and exposed as `__version__`. The build uses Hatch’s version source.

## Python Compatibility

- Supported: Python 3.12, 3.13. CI attempts 3.14 wheels when available.
