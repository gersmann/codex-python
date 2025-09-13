# Repository Guidelines

## Project Structure & Module Organization
- `codex/` – Python package (public API in `__init__.py`, config, client, protocol models).
- `crates/codex_native/` – PyO3 native extension built with maturin (pinned upstream deps).
- `tests/` – `pytest` tests (`test_*.py`).
- `scripts/` – codegen helpers (e.g., `generate_protocol_py.py`).
- `.generated/ts/` – transient TypeScript protocol types. Do not commit hand edits.
- Generated file: `codex/protocol/types.py` – do not edit; run `make gen-protocol`.

## Build, Test, and Development Commands
- Create venv: `make venv` then `. .venv/bin/activate`.
- Format: `make fmt` (ruff format).
- Lint: `make lint` (ruff check --fix + mypy).
- Test: `make test` (pytest; skips if no native ext).
- Build sdist/wheel: `make build` (uv build).
- Native dev install: `make dev-native` (maturin develop or build+pip install).
- Generate protocol: `make gen-protocol` (TS → Pydantic models).
- Prebuild Linux wheels: `make wheelhouse-linux` (manylinux/musllinux via Docker).

## Coding Style & Naming Conventions
- Python 3.12+; type hints required. Line length target: 100.
- Run `make fmt && make lint` before commits.
- Ruff rules: `E,F,I,B,UP` (imports sorted). Mypy: strict-ish (no untyped defs).
- Naming: modules `snake_case.py`, classes `PascalCase`, functions/vars `snake_case`.
- Pydantic v2: prefer `BaseModel`; place `model_config = ConfigDict(extra='allow')` at class end.

## Testing Guidelines
- Framework: `pytest`. Test files: `tests/test_*.py`.
- Write fast, deterministic tests; mock external I/O. Native-dependent tests already skip when the extension is unavailable.
- Example: `uv run --group dev pytest -q` (or `make test`).

## Commit & Pull Request Guidelines
- Use Conventional Commits (e.g., `feat:`, `fix:`, `ci:`, `chore:`). Keep subject ≤72 chars.
- PRs should include: clear description, linked issues, tests (or rationale), and docs/`CHANGELOG.md` updates when user‑visible.
- Keep diffs focused; avoid touching generated files.

## Security & Configuration Tips
- Respect sandbox defaults; avoid introducing commands that assume unrestricted host access.
- Publishing uses UV/PyPI tokens: `UV_PUBLISH_TOKEN` or `PYPI_API_TOKEN` (see `make publish`).
- For local previews, you may set `CODEX_HOME` to a temp dir to isolate state.
