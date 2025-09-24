# codex-python

Native Python bindings for Codex (in‑process execution). Distributed as a single package with prebuilt wheels that bundle the native extension.

- Python: 3.12–3.13 (CI also attempts 3.14)
- Import name: `codex`
- PyPI: https://pypi.org/project/codex-python/

## Table of Contents

1. Install
2. Quickstart
3. API Overview
4. Configuration
   - Common Overrides
   - Examples
5. Troubleshooting
6. Developing
7. CI Integration (Review + Act)

## 1) Install

```
pip install codex-python
```

If there’s no prebuilt wheel for your platform/Python, pip will build from source. That requires a Rust toolchain and maturin; see Developing.

## 2) Quickstart

Run a prompt and collect structured events (typed):

```python
from codex import run_exec, CodexClient, CodexNativeError
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode

cfg = CodexConfig(
    model="gpt-5",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
)

# One‑shot
try:
    events = run_exec("Explain this repo", config=cfg)
    for ev in events:
        print(ev.id, ev.msg.type)
except CodexNativeError as e:
    print("codex-native error:", e)

# Conversation (streaming)
client = CodexClient(config=cfg)
conv = client.start_conversation()
conv.submit_user_turn("Add a smoke test")
for ev in conv:
    print(ev.id, getattr(getattr(ev.msg, "root", ev.msg), "type", "unknown"))
```

Notes
- `Event.msg` is a typed union (`EventMsg`). For raw dicts from the native layer, use `codex.native.start_exec_stream`.

## 3) API Overview

- `codex.run_exec(prompt, *, config=None, load_default_config=True, output_schema=None) -> list[Event]`
  Synchronous one‑shot; returns all events.

- `codex.run_review(prompt, *, user_facing_hint=None, config=None, load_default_config=True) -> list[Event]`
  Synchronous review flow; returns all events.

- `codex.run_prompt(prompt, *, config=None, load_default_config=True, output_schema=None) -> str | Any`
  Convenience: returns the final assistant message (or parsed JSON when `output_schema` is set).

- `codex.CodexClient(config).start_conversation(... ) -> Conversation`
  Creates a stateful session. Iterate over `Conversation` to stream events.
  - `Conversation.submit_user_turn(prompt, *, cwd=None, approval_policy=..., sandbox_mode=..., model=None, effort=..., summary=..., output_schema=None)`
  - `Conversation.submit_review(prompt, user_facing_hint=None)`
  - `Conversation.approve_exec(id, decision)` / `approve_patch(id, decision)`
  - `Conversation.interrupt()`, `Conversation.shutdown()`
  - Utility: `user_input_text`, `override_turn_context`, `add_to_history`, `get_history_entry`, `get_path`, `list_mcp_tools`, `list_custom_prompts`, `compact`

- `await codex.CodexClient(...).astart_conversation() -> AsyncConversation`
  Async iterator with the same methods as `Conversation` (async variants).

- Exceptions
  - `CodexError` base; `CodexNativeError` wraps native failures / missing extension.

- Native helper
  - `codex.native.preview_config(config_overrides, load_default_config)` → compact effective config snapshot (testing aid).

## 4) Configuration

Use the Pydantic model `CodexConfig` for strongly‑typed overrides (mirrors the Rust `ConfigOverrides`).

```python
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

Behavior
- Precedence matches the CLI: `config.toml` < CLI `-c key=value` < typed overrides (`CodexConfig`).
- `to_dict()` emits only set fields and serializes enums to kebab‑case as expected by the native core.
- Set `load_default_config=False` on API calls to avoid reading any on‑disk config and rely purely on overrides you pass in.

### Common Overrides

- Model selection: `model`, `review_model`, `model_provider`.
- Approvals & sandbox: `approval_policy`, `sandbox_mode`, `sandbox_workspace_write` (fine‑tune writeable roots, network, tmpdir behavior for WorkspaceWrite).
- Shell env policy: `shell_environment_policy` for child process envs: `inherit` (`core|all|none`), `exclude`, `include_only`, `set`, `experimental_use_profile`.
- Tools: `include_plan_tool`, `include_apply_patch_tool`, `include_view_image_tool`, `tools_web_search_request`.
- Reasoning & tokens: `model_context_window`, `model_max_output_tokens`, `model_auto_compact_token_limit`, `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`, `model_supports_reasoning_summaries`, `model_reasoning_summary_format`.
- UI/UX: `show_raw_agent_reasoning`, `hide_agent_reasoning`, `disable_paste_burst`, `chatgpt_base_url`, `file_opener`.
- Providers & MCP: `model_providers` entries support `wire_api` (`responses|chat`), `env_key`, `env_key_instructions`, `http_headers`, `env_http_headers`, retry/timeout tuning; `requires_openai_auth` enables ChatGPT/OAuth auth. Define MCP servers via `mcp_servers`.

### Examples

Enable web search and tune sandbox writes:

```python
from codex.config import CodexConfig, ApprovalPolicy, SandboxMode

cfg = CodexConfig(
    model="gpt-5",
    review_model="gpt-5-codex",
    model_provider="openai",
    approval_policy=ApprovalPolicy.ON_REQUEST,
    sandbox_mode=SandboxMode.WORKSPACE_WRITE,
    sandbox_workspace_write={
        "writable_roots": ["/tmp/my-session"],
        "exclude_tmpdir_env_var": True,
    },
    tools_web_search_request=True,
)
```

Constrain child process environment for shell tools:

```python
from codex.config import CodexConfig, ShellEnvironmentPolicy

cfg = CodexConfig(
    shell_environment_policy=ShellEnvironmentPolicy(
        inherit="core",
        exclude=["*TOKEN*", "*KEY*"],
        set={"FOO": "bar"},
        include_only=["PATH", "HOME", "FOO"],
    )
)
```

Provider entry with OAuth‑style auth:

```python
from codex.config import CodexConfig

cfg = CodexConfig(
    model_provider="openai",
    model_providers={
        "openai": {
            "name": "OpenAI",
            "wire_api": "responses",
            "requires_openai_auth": True,
            "request_max_retries": 4,
        }
    }
)
```

## 5) Troubleshooting

- “codex_native extension not installed”
  - Install from PyPI or build locally (see Developing). If building, ensure Rust toolchain + maturin are available.
- No native wheel for your platform/Python
  - Pip will build from source. If that fails, check your Rust toolchain and try `make dev-native` inside a virtualenv.
- Missing `OPENAI_API_KEY`
  - Set the environment variable or configure a provider entry (`model_providers`) that uses a different auth method.

## 6) Developing

Prerequisites
- Python 3.12/3.13
- Rust toolchain (cargo)
- maturin (native builds)
- uv (optional, fast Python builds and dev tooling)

Common tasks
- Format: `make fmt`
- Lint: `make lint` (ruff + mypy)
- Test: `make test` (pytest)
- Build native locally: `make dev-native`
- Generate protocol types from upstream: `make gen-protocol`

Protocol types
- `make gen-protocol` generates TS types + JSON Schema and writes Pydantic v2 models to `codex/protocol/types.py`.
- Generated models include `model_config = ConfigDict(extra='allow')` at class end.

Releasing
- Bump versions in `codex/__init__.py` and `crates/codex_native/Cargo.toml`.
- Update `CHANGELOG.md`.
- Tag and push: `git tag -a vX.Y.Z -m "codex-python X.Y.Z" && git push origin vX.Y.Z`.
- GitHub Actions builds and publishes wheels and sdist via Trusted Publishing.

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
- Codex: https://github.com/openai/codex
- uv: https://docs.astral.sh/uv/
- maturin: https://www.maturin.rs/

## 7) CI Integration: Review + Act

This repo includes a workflow that:
- Runs autonomous code review on PRs ("Review" job).
- Listens for `/codex ...` comments and performs autonomous edits ("Act" job), optionally running your tests.

Both jobs use `gersmann/codex-review-action@v1`.

### Minimal Review Job

```yaml
name: Codex Review
on:
  pull_request:
    types: [opened, synchronize, ready_for_review]
jobs:
  review:
    name: Review
    permissions:
      contents: read
      pull-requests: write
      issues: read
    env:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Codex autonomous review
        if: env.OPENAI_API_KEY != ''
        uses: gersmann/codex-review-action@v1
        with:
          mode: review
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          model: gpt-5
          reasoning_effort: medium
          debug_level: 1
```

### Act on `/codex` Comments

```yaml
  act:
    name: Act on /codex comments
    if: >-
      (
        github.event_name == 'issue_comment' &&
        startsWith(github.event.comment.body, '/codex') &&
        github.event.issue.pull_request &&
        contains(fromJSON('["MEMBER","OWNER","COLLABORATOR"]'), github.event.comment.author_association)
      ) || (
        github.event_name == 'pull_request_review_comment' &&
        startsWith(github.event.comment.body, '/codex') &&
        contains(fromJSON('["MEMBER","OWNER","COLLABORATOR"]'), github.event.comment.author_association)
      )
      && github.actor != 'dependabot[bot]'
    concurrency:
      group: codex-act-${{ github.event.issue.number || github.event.pull_request.number || github.ref }}
      cancel-in-progress: false
    permissions:
      contents: write
      issues: write
      pull-requests: write
      actions: write
    runs-on: ubuntu-latest
    env:
      APP_ENV: test
      CI: true
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.event.pull_request.head.sha || format('refs/pull/{0}/head', github.event.issue.number) }}
          token: ${{ secrets.REPO_ACCESS_TOKEN }}
      - name: Setup Environment
        uses: ./.github/actions/setup
        with:
          python-version: '3.13'
          node-version: '20'
      - name: Codex autonomous edits
        if: env.OPENAI_API_KEY != ''
        uses: gersmann/codex-review-action@v1
        with:
          mode: act
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          model: gpt-5
          debug_level: 1
```

Common `/codex` patterns
- `/codex` — propose and apply fixes
- `/codex focus <path>` — limit scope
- `/codex redo` — re‑run on latest PR head

Secrets
- `OPENAI_API_KEY` to call the model API
- `REPO_ACCESS_TOKEN` (write permission) so pushes from Act trigger CI
- Project‑specific secrets for tests (DB URLs, API keys), when services are enabled
